from pathlib import Path

from transpilex.helpers.logs import Log


def add_gulpfile(project_root: Path, asset_path: str, plugins_config: bool = True):
    """
    Creates a gulpfile.js at the root of the given PHP project.

    Note: The new Gulp script uses its own hardcoded paths and also
    requires a 'plugins.config.js' file to be present.

    Parameters:
    - project_root: Path object pointing to the PHP project root (e.g., 'php/project_name')
    - asset_path: Dictionary with keys 'css', 'scss', 'vendor' (Note: no longer used by this template)
    """

    plugins_import = 'const pluginFile = require("./plugins.config"); // Import the plugins list' if plugins_config else f"""
const pluginFile = {{
    vendorsCSS: [],
    vendorsJS: []
}}
"""

    plugins_fn = """
// Copying Third Party Plugins Assets
const plugins = function () {
    const out = paths.baseDistAssets + "plugins/";

    pluginFile.forEach(({name, vendorsJS, vendorCSS, vendorFonts, assets, fonts, font, media, img, webfonts}) => {

        const handleError = (label, files) => (err) => {
            const shortMsg = err.message.split('\\n')[0];
            console.error(`\\n${label} - ${shortMsg}`);
            throw new Error(` ${label} failed`);
        };

        if (vendorsJS) {
            src(vendorsJS)
                .on('error', handleError('vendorsJS'))
                .pipe(concat("vendors.min.js"))
                .pipe(dest(paths.baseDistAssets + "js/"));
        }

        if (vendorCSS) {
            src(vendorCSS)
                .pipe(concat("vendors.min.css"))
                .on('error', handleError('vendorCSS'))
                .pipe(dest(paths.baseDistAssets + "css/"));
        }

        if (vendorFonts) {
            src(vendorFonts)
                .on('error', handleError('vendorFonts'))
                .pipe(dest(paths.baseDistAssets + "css/fonts/"));
        }

        if (assets) {
            src(assets)
                .on('error', handleError('assets'))
                .pipe(dest(`${out}${name}/`));
        }

        if (img) {
            src(img)
                .on('error', handleError('img'))
                .pipe(dest(`${out}${name}/img/`));
        }

        if (media) {
            src(media)
                .on('error', handleError('media'))
                .pipe(dest(`${out}${name}/`));
        }

        if (fonts) {
            src(fonts)
                .on('error', handleError('fonts'))
                .pipe(dest(`${out}${name}/fonts/`));
        }

        if (font) {
            src(font)
                .on('error', handleError('font'))
                .pipe(dest(`${out}${name}/font/`));
        }

        if (webfonts) {
            src(webfonts)
                .on('error', handleError('webfonts'))
                .pipe(dest(`${out}${name}/webfonts/`));
        }
    });

    return Promise.resolve();
};
    """ if plugins_config else f"""
const vendorStyles = function () {{
const out = paths.baseDistAssets + "/css/";

return src(pluginFile.vendorsCSS, {{sourcemaps: true, allowEmpty: true}})
    .pipe(concat('vendors.css'))
    .pipe(plumber()) // Checks for errors
    .pipe(postcss(processCss))
    .pipe(dest(out))
    .pipe(rename({{suffix: '.min'}}))
    .pipe(postcss(minifyCss)) // Minifies the result
    .pipe(dest(out));
}}


const vendorScripts = function () {{
    const out = paths.baseDistAssets + "/js/";

    return src(pluginFile.vendorsJS, {{sourcemaps: true, allowEmpty: true}})
        .pipe(concat('vendors.js'))
        .pipe(dest(out))
        .pipe(plumber()) // Checks for errors
        .pipe(uglify()) // Minifies the js
        .pipe(rename({{suffix: '.min'}}))
        .pipe(dest(out, {{sourcemaps: '.'}}));
}}
"""

    plugins_task = "plugins," if plugins_config else "vendorStyles, vendorScripts,"

    gulpfile_template = f"""
// Gulp and package
const {{src, dest, parallel, series, watch}} = require('gulp');

// Plugins
const autoprefixer = require('autoprefixer');
const concat = require('gulp-concat');
const tildeImporter = require('node-sass-tilde-importer');
const cssnano = require('cssnano');
const pixrem = require('pixrem');
const plumber = require('gulp-plumber');
const postcss = require('gulp-postcss');
const rename = require('gulp-rename');
const gulpSass = require('gulp-sass');
const dartSass = require('sass');
const gulUglifyES = require('gulp-uglify-es');
const rtlcss = require('gulp-rtlcss');

const sass = gulpSass(dartSass);
const uglify = gulUglifyES.default;

{plugins_import}

const paths = {{
    baseSrcAssets: "{asset_path}",   // source assets directory
    baseDistAssets: "{asset_path}",  // build assets directory
}};


const processCss = [
    autoprefixer(), // adds vendor prefixes
    pixrem(), // add fallbacks for rem units
];

const minifyCss = [
    cssnano({{preset: 'default'}}), // minify result
];

const scss = function () {{
    const out = paths.baseDistAssets + "/css/";

    return src(paths.baseSrcAssets + "/scss/**/*.scss")
        .pipe(
            sass({{
                importer: tildeImporter,
                includePaths: [paths.baseSrcAssets + "/scss"],
            }}).on('error', sass.logError),
        )
        .pipe(plumber()) // Checks for errors
        .pipe(postcss(processCss))
        .pipe(dest(out))
        .pipe(rename({{suffix: '.min'}}))
        .pipe(postcss(minifyCss)) // Minifies the result
        .pipe(dest(out));
}};

const rtl = function () {{
    const out = paths.baseDistAssets + "/css/";

    return src(paths.baseSrcAssets + "/scss/**/*.scss")
        .pipe(
            sass({{
                importer: tildeImporter,
                includePaths: [paths.baseSrcAssets + "/scss"],
            }}).on('error', sass.logError),
        )
        .pipe(plumber()) // Checks for errors
        .pipe(postcss(processCss))
        .pipe(dest(out))
        .pipe(rtlcss())
        .pipe(rename({{suffix: "-rtl.min"}}))
        .pipe(postcss(minifyCss)) // Minifies the result
        .pipe(dest(out));
}};

{plugins_fn}

const watchFiles = function () {{
    watch(paths.baseSrcAssets + "/scss/**/*.scss", series(scss));
}}

// Production Tasks
exports.default = series(
    {plugins_task}
    parallel(scss),
    parallel(watchFiles)
);

// Build Tasks
exports.build = series(
    {plugins_task}
    parallel(scss)
);

// RTL Tasks
exports.rtl = series(
    {plugins_task}
    parallel(rtl),
    parallel(watchFiles)
);

// RTL Build Tasks
exports.rtlBuild = series(
    {plugins_task}
    parallel(rtl),
);
""".strip()

    gulpfile_path = project_root / "gulpfile.js"
    with open(gulpfile_path, "w", encoding="utf-8") as f:
        f.write(gulpfile_template)

    Log.info(f"gulpfile.js is ready at: {gulpfile_path}")
