SOURCE_PATH = "./html"

ASSETS_PATH = "./assets"

SUPPORTED_FRAMEWORKS = ['php', 'laravel', 'cakephp', 'codeigniter', 'symfony', 'node', 'django', 'flask', 'ror', 'core',
                        'mvc',
                        'blazor',
                        'core-to-mvc', 'spring']

FILE_INCLUDE_PREFIX = '@@'
FILE_INCLUDE_COMMAND = 'include'
FILE_INCLUDE_SUFFIX = ''

# PHP
PHP_DESTINATION_FOLDER = 'php'
PHP_SRC_FOLDER = 'src'
PHP_ASSETS_FOLDER = 'assets'
PHP_EXTENSION = '.php'
PHP_GULP_ASSETS_PATH = './src/assets'

# Laravel
LARAVEL_INSTALLER_COMMAND = 'composer global require laravel/installer'
LARAVEL_PROJECT_CREATION_COMMAND = 'laravel new'
LARAVEL_PROJECT_CREATION_COMMAND_AUTH = ['git', 'clone', 'https://github.com/transpilex/laravel-with-auth.git', '.']
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

# Ror
ROR_DESTINATION_FOLDER = 'ror'
ROR_ASSETS_FOLDER = 'frontend'
ROR_EXTENSION = '.html.erb'

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

# Spring
SPRING_PROJECT_CREATION_COMMAND = 'dotnet new webapp -n'
SPRING_DESTINATION_FOLDER = 'spring'
SPRING_ASSETS_FOLDER = 'src/main/resources/static/'
SPRING_EXTENSION = '.html'
SPRING_GULP_ASSETS_PATH = './src/main/resources/static/'
