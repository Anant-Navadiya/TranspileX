from pathlib import Path

def create_gulpfile_js(project_root: Path, asset_paths: str):
    """
    Creates a gulpfile.js at the root of the given PHP project.

    Parameters:
    - project_root: Path object pointing to the PHP project root (e.g., 'php/project_name')
    - asset_paths: Dictionary with keys 'css', 'scss', 'vendor',
    """

    gulpfile_template = f"""
////////////////////////////////
// Setup
////////////////////////////////

const {{src, dest, parallel, series, watch}} = require('gulp');
const autoprefixer = require('autoprefixer');
const browserSync = require('browser-sync').create();
const tildeImporter = require('node-sass-tilde-importer');
const cssnano = require('cssnano');
const pixrem = require('pixrem');
const plumber = require('gulp-plumber');
const postcss = require('gulp-postcss');
const reload = browserSync.reload;
const rename = require('gulp-rename');
const sass = require('gulp-sass')(require('sass'));
const npmdist = require("gulp-npm-dist");

// Relative paths function
function pathsConfig(appName) {{
    return {{
        css: `{asset_paths}/css`,
        scss: `{asset_paths}/scss`,
        vendor: `{asset_paths}/vendor`,
    }};
}}

const paths = pathsConfig();

////////////////////////////////
// Tasks
////////////////////////////////

function styles() {{
    const processCss = [
        autoprefixer(),
        pixrem(),
    ];

    const minifyCss = [
        cssnano({{preset: 'default'}}),
    ];

    return src([`${{paths.scss}}/style.scss`])
        .pipe(
            sass({{
                importer: tildeImporter,
                includePaths: [paths.scss],
            }}).on('error', sass.logError),
        )
        .pipe(plumber())
        .pipe(postcss(processCss))
        .pipe(dest(paths.css))
        .pipe(rename({{suffix: '.min'}}))
        .pipe(postcss(minifyCss))
        .pipe(dest(paths.css));
}}

const plugins = function () {{
    return src(npmdist(), {{base: "./node_modules"}})
        .pipe(rename(function (path) {{
            path.dirname = path.dirname.replace(/\\/dist/, '').replace(/\\\\dist/, '');
        }}))
        .pipe(dest(paths.vendor));
}};

function watchPaths() {{
    watch(`${{paths.scss}}**/**/*.scss`, styles);
    watch([`${{paths.js}}/**/*.js`, `!${{paths.js}}/*.min.js`]).on('change', reload);
}}

const generateAssets = parallel(styles, plugins);
const dev = parallel(watchPaths);

exports.default = series(generateAssets, dev);
exports['generate-assets'] = generateAssets;
exports['dev'] = dev;
""".strip()

    gulpfile_path = project_root / "gulpfile.js"
    with open(gulpfile_path, "w", encoding="utf-8") as f:
        f.write(gulpfile_template)

    print(f"🧪 Created gulpfile.js at: {gulpfile_path}")
