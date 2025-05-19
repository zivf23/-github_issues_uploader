# github_issues_uploader.py
import argparse
import os
import re
from github import Github
from github.GithubException import GithubException

# --- Configuration ---
# It's better to get sensitive info like PAT from environment variables or a config file
# For simplicity in this example, we'll pass it as an argument.
# NEVER hardcode your PAT directly into the script if you plan to commit it.

def parse_markdown_tasks(markdown_file_path: str) -> list[dict]:
    """
    Parses a markdown file containing task definitions.
    Each task should be defined with:
    **Issue Title:** Title of the issue
    **Description:**
    Multiline description...
    **Suggested Labels:** label1, label2
    --- (as a separator between tasks)
    """
    tasks = []
    current_task = {}
    description_lines = []

    try:
        with open(markdown_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()

                title_match = re.match(r"\*\*Issue Title:\*\*\s*(.+)", line, re.IGNORECASE)
                description_marker_match = re.match(r"\*\*Description:\*\*", line, re.IGNORECASE)
                labels_match = re.match(r"\*\*Suggested Labels:\*\*\s*(.+)", line, re.IGNORECASE)
                separator_match = re.match(r"^-{3,}\s*$", line) # Matches '---'

                if title_match:
                    if current_task.get("title"): # Start of a new task, save the previous one
                        if description_lines:
                            current_task["description"] = "\n".join(description_lines).strip()
                            description_lines = []
                        if current_task: # Ensure it's not empty
                             tasks.append(current_task)
                        current_task = {}
                    current_task["title"] = title_match.group(1).strip()
                    current_task["description"] = "" # Initialize description
                    current_task["labels"] = []

                elif description_marker_match:
                    # Start collecting description lines
                    if description_lines: # If there were previous description lines (should not happen with correct format)
                        current_task["description"] = "\n".join(description_lines).strip()
                    description_lines = [] # Reset for new description block

                elif labels_match:
                    if description_lines: # Finalize description before processing labels
                        current_task["description"] = "\n".join(description_lines).strip()
                        description_lines = []
                    labels_str = labels_match.group(1).strip()
                    current_task["labels"] = [label.strip() for label in labels_str.split(',') if label.strip()]
                
                elif separator_match:
                    # End of a task block
                    if current_task.get("title"):
                        if description_lines:
                            current_task["description"] = "\n".join(description_lines).strip()
                            description_lines = []
                        if current_task: # Ensure it's not empty
                            tasks.append(current_task)
                        current_task = {}
                
                elif current_task.get("title") and not labels_match and not title_match:
                    # This line is part of a description if a title has been set
                    # and it's not a label or new title line
                    description_lines.append(line)

            # Add the last task if any
            if current_task.get("title"):
                if description_lines:
                    current_task["description"] = "\n".join(description_lines).strip()
                if current_task:
                    tasks.append(current_task)

    except FileNotFoundError:
        print(f"Error: Markdown file not found at '{markdown_file_path}'")
        return []
    except Exception as e:
        print(f"Error parsing markdown file: {e}")
        return []
        
    return tasks

def create_github_issue(repo, title: str, body: str = None, labels: list[str] = None):
    """
    Creates an issue in the specified GitHub repository.
    """
    try:
        issue_params = {"title": title}
        if body:
            issue_params["body"] = body
        if labels:
            # Ensure labels exist in the repo, or create them if you have perms.
            # For simplicity, this script assumes labels exist or will be handled by GitHub.
            # Alternatively, one could try to create labels if they don't exist:
            # existing_repo_labels = {label.name for label in repo.get_labels()}
            # for label_name in labels:
            #     if label_name not in existing_repo_labels:
            #         try:
            #             repo.create_label(name=label_name, color="ededed") # Default color
            #             print(f"Created label: {label_name}")
            #         except Exception as e_label:
            #             print(f"Could not create label {label_name}: {e_label}")
            issue_params["labels"] = labels
        
        issue = repo.create_issue(**issue_params)
        print(f"Successfully created issue: '{title}' (ID: {issue.id}, URL: {issue.html_url})")
        return True
    except GithubException as e:
        print(f"GitHub API error creating issue '{title}': {e.status} {e.data}")
        return False
    except Exception as e:
        print(f"Failed to create issue '{title}': {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Upload tasks from a markdown file to GitHub Issues.")
    parser.add_argument("markdown_file", help="Path to the markdown file containing tasks.")
    parser.add_argument("repo_name", help="GitHub repository name (e.g., 'owner/repo').")
    parser.add_argument("--token", help="GitHub Personal Access Token. Recommended to use GITHUB_TOKEN env var instead.")
    
    args = parser.parse_args()

    github_token = args.token or os.environ.get("GITHUB_TOKEN")

    if not github_token:
        print("Error: GitHub Personal Access Token not provided.")
        print("Please provide it using --token argument or set GITHUB_TOKEN environment variable.")
        return

    print(f"Parsing tasks from: {args.markdown_file}")
    tasks_to_create = parse_markdown_tasks(args.markdown_file)

    if not tasks_to_create:
        print("No tasks found or error parsing the markdown file.")
        return

    print(f"\nFound {len(tasks_to_create)} tasks to create in repository '{args.repo_name}'.")

    try:
        g = Github(github_token)
        user = g.get_user()
        print(f"Authenticated as GitHub user: {user.login}")
    except Exception as e:
        print(f"Failed to authenticate with GitHub: {e}")
        return

    try:
        repo = g.get_repo(args.repo_name)
        print(f"Successfully connected to repository: {repo.full_name}")
    except GithubException as e:
        print(f"Could not get repository '{args.repo_name}': {e.status} {e.data}")
        print("Please ensure the repository name is correct (e.g., 'owner/repo') and the token has 'repo' scope.")
        return
    except Exception as e:
        print(f"Error accessing repository '{args.repo_name}': {e}")
        return

    created_count = 0
    failed_count = 0

    for task in tasks_to_create:
        title = task.get("title")
        description = task.get("description", "")
        labels = task.get("labels", [])
        
        # Prepend project prefix to labels if needed, e.g. if labels are generic
        # For now, using labels as parsed.

        print(f"\nAttempting to create issue: '{title}'")
        if create_github_issue(repo, title, description, labels):
            created_count += 1
        else:
            failed_count += 1
            
    print(f"\n--- Summary ---")
    print(f"Successfully created {created_count} issues.")
    if failed_count > 0:
        print(f"Failed to create {failed_count} issues.")

if __name__ == "__main__":
    main()
