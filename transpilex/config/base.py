SOURCE_PATH = "./html"

ASSETS_PATH = "./assets"

SUPPORTED_FRAMEWORKS = ['php', 'laravel', 'codeigniter', 'cakephp', 'symfony', 'node', 'django', 'flask', 'core', 'mvc']

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
