SOURCE_PATH = "./html"

ASSETS_PATH = "./assets"

SUPPORTED_FRAMEWORKS = ['php', 'laravel', 'codeigniter', 'cakephp', 'symfony', 'node', 'django', 'flask', 'core', 'mvc',
                        'core-to-mvc']

FILE_INCLUDE_PREFIX = '@@'
FILE_INCLUDE_COMMAND = 'include'
FILE_INCLUDE_SUFFIX = ''

# PHP
PHP_DESTINATION_FOLDER = 'php'
PHP_SRC_FOLDER = 'src'
PHP_ASSETS_FOLDER = 'assets'
PHP_EXTENSION = '.php'
PHP_GULP_ASSETS_PATH = './src/assets'

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

# MVC
MVC_PROJECT_CREATION_COMMAND = 'dotnet new mvc -n'
MVC_DESTINATION_FOLDER = 'mvc'
MVC_ASSETS_FOLDER = 'wwwroot'
MVC_EXTENSION = '.cshtml'
MVC_GULP_ASSETS_PATH = './wwwroot'
