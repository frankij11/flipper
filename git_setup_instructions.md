# Git Setup & Command Line Instructions for Real Estate Flip Finder

## Setting Up Git Repository

1. **Initialize Git repository**

   Navigate to your project directory and initialize a new Git repository:

   ```bash
   cd real_estate_flip_finder
   git init
   ```

2. **Add .gitignore file**

   Create a .gitignore file with the content provided above. This will prevent sensitive credentials, logs, and generated files from being tracked by Git.

   ```bash
   # The .gitignore file has already been created for you
   ```

3. **Create a sample credentials file template**

   Create a template that users can copy and modify with their own credentials:

   ```bash
   cp config/credentials.py config/credentials.template.py
   ```

   Then edit `config/credentials.template.py` to remove any actual credentials and add placeholders.

4. **Make initial commit**

   ```bash
   git add .
   git commit -m "Initial commit of Real Estate Flip Finder"
   ```

5. **Create GitHub repository (optional)**

   Go to GitHub and create a new repository. Then, link your local repository:

   ```bash
   git remote add origin https://github.com/yourusername/real-estate-flip-finder.git
   git branch -M main
   git push -u origin main
   ```

## Using the Application from Command Prompt

1. **Set up virtual environment**

   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure credentials**

   ```bash
   # Copy the template (if not already done)
   cp config/credentials.template.py config/credentials.py

   # Edit credentials.py with your favorite editor
   # Windows example:
   notepad config\credentials.py

   # macOS/Linux example:
   nano config/credentials.py
   ```

4. **Run the application**

   Basic usage with Bright MLS:
   ```bash
   python main.py --area "20878" --budget 400000 --roi 20 --source mls --export --visualize
   ```

   Using Redfin data:
   ```bash
   python main.py --area "20878" --budget 400000 --roi 20 --source redfin --export --visualize
   ```

   Using both data sources:
   ```bash
   python main.py --area "20878" --budget 400000 --roi 20 --source both --export --visualize
   ```

   View all available options:
   ```bash
   python main.py --help
   ```

5. **View results**

   After running the application, check:
   - The terminal output for a summary of top properties
   - The `output/excel/` directory for Excel reports
   - The `output/dashboards/` directory for interactive HTML dashboards

## Common Git Commands for Development

1. **Check status of your changes**

   ```bash
   git status
   ```

2. **Create a new branch for a feature**

   ```bash
   git checkout -b feature/new-data-source
   ```

3. **Commit your changes**

   ```bash
   git add .
   git commit -m "Add new data source for Zillow"
   ```

4. **Push changes to GitHub**

   ```bash
   git push origin feature/new-data-source
   ```

5. **Merge changes back to main branch**

   ```bash
   git checkout main
   git merge feature/new-data-source
   git push origin main
   ```

## Troubleshooting

1. **If credentials aren't working:**
   - Ensure `config/credentials.py` has your valid API keys
   - Check that you're using the correct format for each API

2. **If data sources aren't returning results:**
   - Try with a different ZIP code or area name
   - Increase your budget parameter
   - Check if the service APIs are currently available

3. **If Git operations fail:**
   - Make sure your repository remotes are correctly configured:
     ```bash
     git remote -v
     ```
   - Ensure you have necessary permissions for the repository
