SOURCE_PATH = "./html"

ASSETS_PATH = "./assets"

SUPPORTED_FRAMEWORKS = ['php', 'laravel', 'cakephp', 'codeigniter', 'symfony', 'node', 'django', 'flask', 'ror',
                        'spring' 'core',
                        'mvc',
                        'blazor',
                        'core-to-mvc']

# PHP
PHP_DESTINATION_FOLDER = 'php'
PHP_SRC_FOLDER = 'src'
PHP_ASSETS_FOLDER = 'assets'
PHP_EXTENSION = '.php'
PHP_GULP_ASSETS_PATH = './src/assets'

# Laravel
LARAVEL_INSTALLER_COMMAND = 'composer global require laravel/installer'
LARAVEL_PROJECT_CREATION_COMMAND = 'laravel new'
LARAVEL_PROJECT_CREATION_COMMAND_AUTH = ['git', 'clone',
                                         'https://github.com/transpilex/laravel-boilerplate-with-auth.git', '.']
LARAVEL_DESTINATION_FOLDER = 'laravel'
LARAVEL_EXTENSION = '.blade.php'
LARAVEL_ASSETS_FOLDER = 'resources'
LARAVEL_RESOURCES_PRESERVE = ["views"]
LARAVEL_GULP_ASSETS_PATH = './public'
LARAVEL_AUTH_FOLDER = 'default-auth'

# CakePHP
CAKEPHP_PROJECT_CREATION_COMMAND = 'composer create-project --prefer-dist cakephp/app:~5.0'
CAKEPHP_DESTINATION_FOLDER = 'cakephp'
CAKEPHP_EXTENSION = '.php'
CAKEPHP_ASSETS_FOLDER = 'webroot'
CAKEPHP_ASSETS_PRESERVE = ["index.php", ".htaccess"]
CAKEPHP_GULP_ASSETS_PATH = './webroot'

# CodeIgniter
CODEIGNITER_PROJECT_CREATION_COMMAND = 'composer create-project codeigniter4/appstarter'
CODEIGNITER_DESTINATION_FOLDER = 'codeigniter'
CODEIGNITER_EXTENSION = '.php'
CODEIGNITER_ASSETS_FOLDER = 'public'
CODEIGNITER_ASSETS_PRESERVE = ["index.php", ".htaccess", "manifest.json", "robots.txt"]
CODEIGNITER_GULP_ASSETS_PATH = './public'

# Symfony
SYMFONY_INSTALLATION_VERSION = "7.3.x-dev"
SYMFONY_DESTINATION_FOLDER = 'symfony'
SYMFONY_EXTENSION = '.html.twig'
SYMFONY_ASSETS_FOLDER = 'public'
SYMFONY_ASSETS_PRESERVE = ["index.php"]
SYMFONY_GULP_ASSETS_PATH = './public'

# Node
NODE_DESTINATION_FOLDER = 'node'
NODE_EXTENSION = '.ejs'
NODE_ASSETS_FOLDER = 'public'
NODE_GULP_ASSETS_PATH = './public'

# Django
DJANGO_COOKIECUTTER_REPO = 'https://github.com/transpilex/cookiecutter-django.git'
DJANGO_DESTINATION_FOLDER = 'django'
DJANGO_ASSETS_FOLDER = 'static'
DJANGO_EXTENSION = '.html'

# Flask
FLASK_PROJECT_CREATION_COMMAND = ['git', 'clone', 'https://github.com/transpilex/flask-boilerplate.git', '.']
FLASK_PROJECT_CREATION_COMMAND_AUTH = ['git', 'clone', 'https://github.com/transpilex/flask-boilerplate-with-auth.git',
                                       '.']
FLASK_DESTINATION_FOLDER = 'flask'
FLASK_ASSETS_FOLDER = 'apps/static'
FLASK_EXTENSION = '.html'
FLASK_GULP_ASSETS_PATH = './apps/static'

# RoR
ROR_PROJECT_CREATION_COMMAND = ['git', 'clone', 'https://github.com/transpilex/ror-boilerplate.git', '.']
ROR_DESTINATION_FOLDER = 'ror'
ROR_ASSETS_FOLDER = 'frontend'
ROR_EXTENSION = '.html.erb'
ROR_ASSETS_PRESERVE = ['entrypoints']

# Spring Boot
SPRING_BOOT_PROJECT_CREATION_URL = 'https://start.spring.io/starter.zip'
SPRING_BOOT_DESTINATION_FOLDER = 'spring'
SPRING_BOOT_EXTENSION = '.html'
SPRING_BOOT_ASSETS_FOLDER = "static"
SPRING_TEMPLATES_FOLDER = "templates"
SPRING_JAVA_SOURCE_FOLDER = "src/main/java"
SPRING_RESOURCES_FOLDER = "src/main/resources"
SPRING_BOOT_GULP_ASSETS_PATH = './src/main/resources/static'
SPRING_BOOT_GROUP_ID = "com"
SPRING_BOOT_PROJECT_PARAMS = {
    "type": "maven-project",
    "language": "java",
    "bootVersion": "3.5.3",
    "groupId": SPRING_BOOT_GROUP_ID,
    "packaging": "jar",
    "javaVersion": "24",
    "dependencies": "web,thymeleaf,devtools",
}

# Dot Net
SLN_FILE_CREATION_COMMAND = 'dotnet new sln -n'

# Core
CORE_PROJECT_CREATION_COMMAND = 'dotnet new razor -n'
CORE_DESTINATION_FOLDER = 'core'
CORE_ASSETS_FOLDER = 'wwwroot'
CORE_EXTENSION = '.cshtml'
CORE_ADDITIONAL_EXTENSION = '.cshtml.cs'
CORE_GULP_ASSETS_PATH = './wwwroot'

# MVC
MVC_PROJECT_CREATION_COMMAND = 'dotnet new mvc -n'
MVC_DESTINATION_FOLDER = 'mvc'
MVC_ASSETS_FOLDER = 'wwwroot'
MVC_EXTENSION = '.cshtml'
MVC_GULP_ASSETS_PATH = './wwwroot'

# Blazor
BLAZOR_PROJECT_CREATION_COMMAND = 'dotnet new blazor -o'
BLAZOR_DESTINATION_FOLDER = 'blazor'
BLAZOR_ASSETS_FOLDER = 'wwwroot'
BLAZOR_EXTENSION = '.razor'
BLAZOR_GULP_ASSETS_PATH = './wwwroot'

TITLE_KEYS = ["title", "pageTitle"]
SUBTITLE_KEYS = ["subtitle", "subTitle", "pageSubText"]

FILENAME_PRIORITY = [
    'page-title.html',
    'app-pagetitle.html',
    'title-meta.html',
    'app-meta-title.html'
]
