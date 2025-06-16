def create_core_project(project_name, source_folder, assets_folder):
    """
    1. Create a new Core project using Composer.
    2. Copy all files from the source_folder to the new project's templates/Pages folder.
    3. Convert the includes to Codeigniter-style using convert_to_codeigniter().
    4. Add HomeController.php to the Controllers folder.
    5. Patch routes.
    6. Copy custom assets to public, preserving required files.
    """
    
    project_root = Path("core") / project_name
    project_root.parent.mkdir(parents=True, exist_ok=True)

    # Create the Codeigniter project using Composer
    print(f"📦 Creating Codeigniter project '{project_root}'...")
     try:
        subprocess.run(
            f'composer create-project codeigniter4/appstarter {project_root}',
            shell=True,
            check=True
        )
        print("✅ Codeigniter project created successfully.")

    except subprocess.CalledProcessError:
        print("❌ Error: Could not create Codeigniter project. Make sure Composer and PHP are set up correctly.")
        return