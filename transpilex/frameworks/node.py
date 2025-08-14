import re
import json
import ast
from pathlib import Path

from transpilex.config.base import NODE_ASSETS_FOLDER, NODE_DESTINATION_FOLDER, NODE_EXTENSION, NODE_GULP_ASSETS_PATH, \
    FILENAME_PRIORITY, TITLE_KEYS
from transpilex.helpers import change_extension_and_copy, copy_assets
from transpilex.helpers.gulpfile import add_gulpfile
from transpilex.helpers.add_plugins_file import add_plugins_file
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.logs import Log
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.package_json import sync_package_json
from transpilex.helpers.validations import folder_exists


class NodeConverter:
    def __init__(self, project_name: str, source_path: str, assets_path: str, include_gulp: bool = True,
                 plugins_config: bool = True):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(NODE_DESTINATION_FOLDER)
        self.assets_path = Path(self.source_path / assets_path)
        self.include_gulp = include_gulp
        self.plugins_config = plugins_config

        self.project_root = self.destination_path / project_name
        self.project_assets_path = self.project_root / NODE_ASSETS_FOLDER
        self.project_views_path = Path(self.project_root / "views")
        self.project_routes_path = Path(self.project_root / "routes")

        self.project_root.mkdir(parents=True, exist_ok=True)

        self.create_project()

    def create_project(self):

        if not folder_exists(self.source_path):
            Log.error("Source folder does not exist")
            return

        if folder_exists(self.project_root):
            Log.error(f"Project already exists at: {self.project_root}")
            return

        Log.project_start(self.project_name)

        change_extension_and_copy(NODE_EXTENSION, self.source_path, self.project_views_path)

        self._create_routes()

        self._convert()

        self._replace_partial_variables()

        self._create_app_js()

        copy_assets(self.assets_path, self.project_assets_path)

        if self.include_gulp:
            add_gulpfile(self.project_root, NODE_GULP_ASSETS_PATH, self.plugins_config)

        if self.include_gulp and self.plugins_config:
            add_plugins_file(self.source_path, self.project_root)

        sync_package_json(self.source_path, self.project_root,
                          ignore_gulp=not self.include_gulp,
                          extra_fields={
                              "scripts": {
                                  "start": "npm-run-all preview",
                                  "preview": "nodemon app.js"
                              },
                          },
                          extra_plugins={"cookie-parser": None, "ejs": None, "express": None,
                                         "express-ejs-layouts": None, "express-fileupload": None,
                                         "express-session": None, "nodemon": None, "npm-run-all": None, "path": None})

        Log.project_end(self.project_name, str(self.project_root))

    def _convert(self):
        """
        Convert all @@include(...) in .html files to <%- include(...) %> (EJS syntax)
        using a single, unified regular expression.
        """
        count = 0

        def strip_extension(path):
            """
            Strip .html or .htm extension from a path string
            """
            return re.sub(r'\.html?$', '', path)

        for file in self.project_views_path.rglob("*"):
            if file.is_file() and file.suffix in ['.html', '.ejs']:
                original = file.read_text(encoding="utf-8")
                content = original

                # expression finds an @@include, captures the path (group 1),
                # and optionally matches (and discards) a data block.
                content = re.sub(
                    r"@@include\(['\"](.+?)['\"]\s*(?:,\s*\{.*?\}\s*)?\)",
                    lambda m: f"<%- include('{strip_extension(m.group(1))}') %>",
                    content,
                    flags=re.DOTALL
                )

                content = replace_html_links(content, '')
                content = clean_relative_asset_paths(content)

                if content != original:
                    file.write_text(content, encoding="utf-8")
                    Log.converted(str(file))
                    count += 1

        Log.info(f"{count} files converted in {self.project_views_path}")

    def _extract_meta(self, content: str):
        """
        Extracts metadata from the highest-priority @@include statement in the content.
        Now returns the entire cleaned data object.
        """
        # The first part of the function (pattern, matches, sorting) remains the same.
        pattern = re.compile(
            r"""@@include\(\s*
                ['"](?P<path>.*?)['"]\s*,\s* # Capture the file path
                (?P<data_str>\{.*?\})\s* # Capture the data object string
                \)\s*""",
            re.VERBOSE | re.DOTALL
        )

        matches = list(pattern.finditer(content))
        if not matches:
            return {}

        def get_priority(match):
            path = match.group('path').split('/')[-1]
            try:
                return FILENAME_PRIORITY.index(path)
            except ValueError:
                return len(FILENAME_PRIORITY)

        matches.sort(key=get_priority)

        # Process matches in order of priority
        for match in matches:
            data_str = match.group('data_str')
            try:
                data = ast.literal_eval(data_str)
            except (ValueError, SyntaxError):
                continue

            # Check if at least one of the known title keys exists.
            if any(key in data for key in TITLE_KEYS):
                # clean ALL values and return the whole dictionary.
                cleaned_data = {}
                for key, value in data.items():
                    if isinstance(value, str):
                        # Collapse whitespace (like newlines) into a single space
                        cleaned_data[key] = ' '.join(value.split())
                    else:
                        # Keep non-string values (numbers, booleans) as-is
                        cleaned_data[key] = value
                return cleaned_data

        return {}

    def _add_route(self, file_name, meta):
        """
        Generates a route that passes the entire meta object to the template.
        """
        route_path = "/" if file_name == "index" else f"/{file_name}"
        route = f"route.get('{route_path}', (req, res, next) => {{\n"

        render_line = f"    res.render('{file_name}'"

        if meta:
            js_object_parts = []
            for key, value in meta.items():
                # Use json.dumps to safely convert the Python value to a
                # JavaScript-compatible value string. It handles quotes, booleans, etc.
                js_value = json.dumps(value)
                js_object_parts.append(f"{key}: {js_value}")

            # Join all the key: value pairs with commas
            js_object_string = ", ".join(js_object_parts)
            render_line += f", {{ {js_object_string} }}"

        render_line += ");"
        route += render_line + "\n});\n"
        return route

    def _create_routes(self):

        if not self.project_views_path.exists():
            Log.error(f"Folder '{self.project_views_path}' not found")
            return

        self.project_routes_path.mkdir(parents=True, exist_ok=True)

        route_file = self.project_routes_path / 'index.js'

        routes = [
            "const express = require('express');",
            "const route = express.Router();\n"
        ]

        skipped = []

        for file in self.project_views_path.glob("*.ejs"):
            content = file.read_text(encoding="utf-8")
            file_name = file.stem
            meta = self._extract_meta(content)

            if not any(key in meta for key in TITLE_KEYS):
                Log.warning(f"Skipping: {file_name}.ejs as no title key found")
                skipped.append(file_name)
                continue

            route_code = self._add_route(file_name, meta)
            routes.append(route_code)

        routes.append("\nmodule.exports = route;")
        route_file.write_text("\n".join(routes), encoding="utf-8")

        Log.created(f"route.js at {self.project_routes_path}")
        if skipped:
            Log.warning(f"Skipped files with no meta: {', '.join(skipped)}")

    def _create_app_js(self):
        """Creates the main app.js file in the project root"""
        app_js_path = self.project_root / 'app.js'

        # The content for the app.js file
        content = """const express = require('express');
const app = express();
const path = require('path');
const expressLayouts = require('express-ejs-layouts');
const session = require('express-session');
const cookieParser = require('cookie-parser');
const upload = require('express-fileupload');
const route = require('./routes/index');

app.set('views', path.join(__dirname, '/views'));
app.set('view engine', 'ejs');
app.use(upload());

app.use(express.json());
app.use(session({ resave: false, saveUninitialized: true, secret: 'nodedemo' }));
app.use(cookieParser());

app.use(express.static(__dirname + '/public'));

app.use('/', route);

const http = require("http").createServer(app);

const port = 3000

http.listen(port, () => {
    console.log(`Server running on port ${port}`)
    console.log(`http://localhost:${port}`)
});
    """
        app_js_path.write_text(content, encoding="utf-8")
        Log.created(f"app.js at {self.project_root}")

    def _replace_partial_variables(self):
        count = 0
        pattern = re.compile(r'@@(?!if\b|include\b)([A-Za-z_]\w*)\b')

        for file in self.project_views_path.rglob(f"*{NODE_EXTENSION}"):
            if not file.is_file():
                continue
            try:
                content = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            new_content = pattern.sub(r'<%- \1 %>', content)
            if new_content != content:
                file.write_text(new_content, encoding="utf-8")
                Log.updated(str(file))
                count += 1

        if count:
            Log.info(f"{count} files updated in {self.project_views_path}")
