# TranspileX

**TranspileX** is a command-line utility to convert HTML templates into structured codebases for various popular backend frameworks like Laravel, Django, Flask, Symfony, and more.

## 🧩 Supported Frameworks

- PHP
- Laravel
- Symfony
- CodeIgniter
- CakePHP
- Django
- Flask
- Node.js
- Core
- MVC

## 🚀 Installation

```bash
pip install transpilex
```

Or for global usage:

```bash
pipx install transpilex
```

## 🛠️ Usage

By default, TranspileX expects:

- All your HTML files inside an `html/` folder.
- All your static assets (CSS, JS, images) inside an `assets/` folder.

You can change these paths via command-line arguments if needed.

```bash
transpile project_name laravel
```

## 📂 Options

| Argument        | Description                                   |
|-----------------|-----------------------------------------------|
| `--src`   | Path to source HTML template folder           |
| `--assets` | Path to assets folder                         |

## 🔧 Features

- Automatic asset copying
- HTML link restructuring
- Dynamic gulpfile and package.json updates
- Extension and structure conversion


## 📄 License

MIT License.
