from pathlib import Path

from transpilex.helpers.messages import Messenger


def add_gulpfile(project_root: Path, asset_path: str):
    """
    Creates a gulpfile.js at the root of the given PHP project.

    Note: The new Gulp script uses its own hardcoded paths and also
    requires a 'plugins.config.js' file to be present.

    Parameters:
    - project_root: Path object pointing to the PHP project root (e.g., 'php/project_name')
    - asset_path: Dictionary with keys 'css', 'scss', 'vendor' (Note: no longer used by this template)
    """
    gulpfile_template = f"""
const {{series, src, dest, parallel, watch}} = require("gulp");

const autoprefixer = require("gulp-autoprefixer");
const concat = require("gulp-concat");
const CleanCSS = require("gulp-clean-css");
const rename =require("gulp-rename");
const rtlcss = require("gulp-rtlcss");
const sourcemaps = require("gulp-sourcemaps");
const sass = require("gulp-sass")(require("sass"));

const pluginFile = require("./plugins.config"); // Import the plugins list

const paths = {{
    baseDistAssets: "{asset_path}",  // build assets directory
    baseSrcAssets: "{asset_path}",   // source assets directory
}};

// Copying Third Party Plugins Assets
const plugins = function () {{
    const out = paths.baseDistAssets + "plugins/";

    pluginFile.forEach(({{name, vendorsJS, vendorCSS, vendorFonts, assets, fonts, font, media, img, webfonts}}) => {{

        const handleError = (label, files) => (err) => {{
            const shortMsg = err.message.split('\\n')[0];
            console.error(`\\n${{label}} - ${{shortMsg}}`);
            throw new Error(` ${{label}} failed`);
        }};

        if (vendorsJS) {{
            src(vendorsJS)
                .on('error', handleError('vendorsJS'))
                .pipe(concat("vendors.min.js"))
                .pipe(dest(paths.baseDistAssets + "js/"));
        }}

        if (vendorCSS) {{
            src(vendorCSS)
                .pipe(concat("vendors.min.css"))
                .on('error', handleError('vendorCSS'))
                .pipe(dest(paths.baseDistAssets + "css/"));
        }}

        if (vendorFonts) {{
            src(vendorFonts)
                .on('error', handleError('vendorFonts'))
                .pipe(dest(paths.baseDistAssets + "css/fonts/"));
        }}

        if (assets) {{
            src(assets)
                .on('error', handleError('assets'))
                .pipe(dest(`${{out}}${{name}}/`));
        }}

        if (img) {{
            src(img)
                .on('error', handleError('img'))
                .pipe(dest(`${{out}}${{name}}/img/`));
        }}

        if (media) {{
            src(media)
                .on('error', handleError('media'))
                .pipe(dest(`${{out}}${{name}}/`));
        }}


        if (fonts) {{
            src(fonts)
                .on('error', handleError('fonts'))
                .pipe(dest(`${{out}}${{name}}/fonts/`));
        }}

        if (font) {{
            src(font)
                .on('error', handleError('font'))
                .pipe(dest(`${{out}}${{name}}/font/`));
        }}

        if (webfonts) {{
            src(webfonts)
                .on('error', handleError('webfonts'))
                .pipe(dest(`${{out}}${{name}}/webfonts/`));
        }}
    }});

    return Promise.resolve();
}};

const scss = function () {{
    const out = paths.baseDistAssets + "css/";

    return src(paths.baseSrcAssets + "scss/**/*.scss")
        .pipe(sourcemaps.init())
        .pipe(sass.sync().on('error', sass.logError)) // scss to css
        .pipe(
            autoprefixer({{
                overrideBrowserslist: ["last 2 versions"],
            }})
        )
        .pipe(dest(out))
        .pipe(CleanCSS())
        .pipe(rename({{suffix: ".min"}}))
        .pipe(sourcemaps.write("./")) // source maps
        .pipe(dest(out));
}};

const rtl = function () {{
    const out = paths.baseDistAssets + "css/";

    return src(paths.baseSrcAssets + "scss/**/*.scss")
        .pipe(sourcemaps.init())
        .pipe(sass.sync().on('error', sass.logError)) // scss to css
        .pipe(
            autoprefixer({{
                overrideBrowserslist: ["last 2 versions"],
            }})
        )
        .pipe(rtlcss())
        .pipe(rename({{suffix: "-rtl"}}))
        .pipe(dest(out))
        .pipe(CleanCSS())
        .pipe(rename({{suffix: ".min"}}))
        .pipe(sourcemaps.write("./")) // source maps
        .pipe(dest(out));
}};


function watchFiles() {{
    watch(paths.baseSrcAssets + "scss/**/*.scss", series(scss));
}}

// Production Tasks
exports.default = series(
    plugins,
    parallel(scss),
    parallel(watchFiles)
);

// Build Tasks
exports.build = series(
    plugins,
    parallel(scss)
);

// RTL Tasks
exports.rtl = series(
    plugins,
    parallel(rtl),
    parallel(watchFiles)
);

// RTL Build Tasks
exports.rtlBuild = series(
    plugins,
    parallel(rtl),
);
""".strip()

    gulpfile_path = project_root / "gulpfile.js"
    with open(gulpfile_path, "w", encoding="utf-8") as f:
        f.write(gulpfile_template)

    Messenger.success(f"Created gulpfile.js at: {gulpfile_path}")
