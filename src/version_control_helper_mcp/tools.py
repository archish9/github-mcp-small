"""MCP tool implementations for version control operations."""

from pathlib import Path
from mcp.server.fastmcp import FastMCP
from mcp.types import Tool, TextContent

from .git_utils import GitManager
from .models import CommitList, CommitDiff, BranchInfo, RepoStatus


def register_tools(mcp: FastMCP, default_repo_path: str | None = None):
    """Register all MCP tools on the server.
    
    Args:
        mcp: MCP server instance
        default_repo_path: Default repository path (can be overridden per-call)
    """
    
    def get_manager(repo_path: str | None = None) -> GitManager:
        """Get GitManager for the specified or default repo path."""
        path = repo_path or default_repo_path
        if not path:
            raise ValueError("repo_path is required (no default configured)")
        return GitManager(path)

    @mcp.tool()
    async def initialize_repo(
        repo_path: str,
        initial_commit: bool = True,
    ) -> str:
        """Initialize a new git repository at the specified path.
        
        This tool creates a `.git` directory at `repo_path` if it doesn't already exist.
        It is safe to call on an existing repository (it will return a success message without modifying the repo).
        
        Args:
            repo_path: The absolute path to the directory where the git repository should be initialized.
                       If the directory does not exist, it will be created.
            initial_commit: If True, and the repository is empty or fresh, an initial commit will be created.
                            This includes creating a README.md if one doesn't exist.
                            Default is True.
        
        Returns:
            A status message indicating whether the repository was initialized, 
            already existed, or if an initial commit was created.
        """
        manager = GitManager(repo_path)
        return manager.initialize(initial_commit=initial_commit)

    @mcp.tool()
    async def get_repo_status(repo_path: str) -> str:
        """Get the current status of the git repository.
        
        This tool provides a snapshot of the repository's state, including:
        - Initialization status (is it a git repo?)
        - Current branch name
        - Whether there are uncommitted changes
        - Lists of staged, modified, and untracked files
        
        Use this tool before committing to verify what changes will be included,
        or to simply check the current context (branch, pending changes).
        
        Args:
            repo_path: The absolute path to the repository.
            
        Returns:
            A JSON-formatted string containing the repository status details.
            
            Example JSON structure:
            {
              "is_initialized": true,
              "current_branch": "main",
              "has_changes": true,
              "staged_files": ["file1.py"],
              "modified_files": ["file2.py"],
              "untracked_files": ["new_file.py"]
            }
        """
        manager = GitManager(repo_path)
        status = manager.get_status()
        return status.model_dump_json(indent=2)

    @mcp.tool()
    async def commit_all_changes(
        repo_path: str,
        message: str,
    ) -> str:
        """Stage ALL changes (including untracked files) and create a commit.
        
        This tool acts as a "save point" for the project. It performs the equivalent of:
        1. `git add -A` (Stages all modified, deleted, and new files)
        2. `git commit -m "message"`
        
        It will automatically initialize the repository if it hasn't been initialized yet.
        
        Args:
            repo_path: The absolute path to the repository.
            message: A descriptive commit message. 
                     Common prefixes: 'feat:', 'fix:', 'docs:', 'refactor:', 'test:'.
            
        Returns:
            The SHA (full hash) of the new commit, or a message indicating "No changes to commit" 
            if the working directory was clean.
        """
        manager = GitManager(repo_path)
        
        # Lazy initialization for mutating operations
        if not manager.is_initialized():
            manager.initialize(initial_commit=False)
        
        return manager.commit_all(message)

    @mcp.tool()
    async def list_commits(
        repo_path: str,
        branch: str = "HEAD",
        limit: int = 50,
    ) -> str:
        """List the commit history for a specific branch or reference.
        
        Retrieves a list of commits starting from the specified `branch` (or HEAD),
        going back in history up to `limit`. Each commit includes:
        - SHA (full and short)
        - Message
        - Author details
        - Timestamp
        
        Args:
            repo_path: The absolute path to the repository.
            branch: The branch name, tag, or commit SHA to start listing from. 
                    Defaults to "HEAD" (current checkout).
            limit: The maximum number of commits to return. Defaults to 50.
            
        Returns:
            A JSON-formatted string containing a list of commit objects.
        """
        manager = get_manager(repo_path)
        commits = manager.list_commits(branch=branch, limit=limit)
        return commits.model_dump_json(indent=2)

    @mcp.tool()
    async def rollback_to_commit(
        repo_path: str,
        commit_sha: str,
        mode: str = "soft",
    ) -> str:
        """Roll back the repository state to a previous commit.
        
        This tool resets the current branch head to `commit_sha`. The `mode` determines 
        what happens to the working directory and index:
        
        - "soft" (Default): Undoes the commit(s) but leaves changes staged in the index.
          Useful if you want to squash commits or fix the last commit message.
          
        - "mixed": Undoes the commit(s) and unstages changes, but keeps the files in the working directory.
          Useful if you want to keep the work but start fresh with staging.
          
        - "hard": WARNING - Destructive! Resets everything to the state of `commit_sha`.
          Any uncommitted changes (staged or unstaged) will be PERMANENTLY LOST.
          Use this only if you want to discard all work since `commit_sha`.
        
        Args:
            repo_path: The absolute path to the repository.
            commit_sha: The full or short SHA of the commit to revert to.
            mode: The reset mode: "soft", "mixed", or "hard".
            
        Returns:
            A message confirming the rollback and the new HEAD SHA.
        """
        manager = get_manager(repo_path)
        new_head = manager.rollback(commit_sha=commit_sha, mode=mode)
        return f"Rolled back to {commit_sha[:7]}. New HEAD: {new_head[:7]} (mode: {mode})"

    @mcp.tool()
    async def compare_commits(
        repo_path: str,
        from_commit: str,
        to_commit: str,
    ) -> str:
        """Compare two commits and return the diff.
        
        This tool generates a detailed comparison between two points in the history (`from_commit` -> `to_commit`).
        It's useful for:
        - Reviewing changes between versions.
        - Debugging when a bug was introduced.
        - Generating a changelog.
        
        The output includes a summary of file changes (added, modified, deleted, renamed)
        and the actual diff content for each file.
        
        Args:
            repo_path: The absolute path to the repository.
            from_commit: The source (older) commit SHA.
            to_commit: The target (newer) commit SHA.
            
        Returns:
            A JSON-formatted string containing the list of changed files, 
            additions/deletions counts, and diff patches.
        """
        manager = get_manager(repo_path)
        diff = manager.compare_commits(from_sha=from_commit, to_sha=to_commit)
        return diff.model_dump_json(indent=2)

    @mcp.tool()
    async def create_branch(
        repo_path: str,
        branch_name: str,
        from_ref: str | None = None,
    ) -> str:
        """Create a new git branch.
        
        This tool creates a new branch pointer but DOES NOT switch to it. 
        To start working on the new branch, you must call `switch_branch` afterwards.
        
        Args:
            repo_path: The absolute path to the repository.
            branch_name: The name of the new branch (e.g., "feature/new-login").
            from_ref: The commit SHA or branch name to start the new branch from.
                      If not provided, defaults to the current HEAD.
            
        Returns:
            A confirmation message containing the new branch name.
        """
        manager = get_manager(repo_path)
        name = manager.create_branch(branch_name=branch_name, from_ref=from_ref)
        return f"Created branch: {name}"

    @mcp.tool()
    async def switch_branch(
        repo_path: str,
        branch_name: str,
    ) -> str:
        """Switch the repository to a different branch.
        
        This command updates the working directory to match the state of the specified branch.
        It performs a `git checkout`.
        
        Args:
            repo_path: The absolute path to the repository.
            branch_name: The name of the branch to switch to.
                         The branch must already exist.
            
        Returns:
            A confirmation message indicating the successful switch and current branch name.
        """
        manager = get_manager(repo_path)
        current = manager.switch_branch(branch_name=branch_name)
        return f"Switched to branch: {current}"

    @mcp.tool()
    async def list_branches(repo_path: str) -> str:
        """List all branches in the repository.
        
        Shows all local branches with current branch marked.
        
        Args:
            repo_path: Path to the repository directory
            
        Returns:
            JSON list of branches with current branch indicator
        """
        manager = get_manager(repo_path)
        branches = manager.list_branches()
        return "\n".join([
            f"{'* ' if b.is_current else '  '}{b.name} ({b.last_commit_sha}): {b.last_commit_message}"
            for b in branches
        ])

    @mcp.tool()
    async def generate_commit_message(
        repo_path: str,
        style: str = "conventional",
    ) -> str:
        """Generate a suggested commit message based on staged changes.
        
        This tool analyzes the staged and modified files to suggest a commit message.
        Note: This uses a simple heuristic (template-based), not a full LLM analysis of the diff content.
        It is useful as a starting point or for quick commits.
        
        Styles:
        - "conventional": Uses Conventional Commits format (feat: ..., fix: ..., chore: ...) based on file types.
        - "simple": Returns a plain predictive sentence like "Update 3 files".
        
        Args:
            repo_path: The absolute path to the repository.
            style: The message style format to use. Defaults to "conventional".
            
        Returns:
            A string containing the suggested commit message and a brief summary of detected changes.
        """
        manager = get_manager(repo_path)
        status = manager.get_status()
        
        if not status.has_changes:
            return "No changes to describe"
        
        # Build a description of changes
        changes = []
        if status.staged_files:
            changes.append(f"Staged: {', '.join(status.staged_files[:5])}")
            if len(status.staged_files) > 5:
                changes.append(f"  ...and {len(status.staged_files) - 5} more")
        if status.modified_files:
            changes.append(f"Modified: {', '.join(status.modified_files[:5])}")
        if status.untracked_files:
            changes.append(f"New: {', '.join(status.untracked_files[:5])}")
        
        # Simple heuristic-based message generation
        # In a real implementation, this could call an LLM
        file_count = len(status.staged_files) + len(status.modified_files) + len(status.untracked_files)
        
        if style == "conventional":
            if status.untracked_files:
                prefix = "feat"
            elif any("test" in f.lower() for f in status.modified_files + status.staged_files):
                prefix = "test"
            elif any("readme" in f.lower() or "doc" in f.lower() for f in status.modified_files + status.staged_files):
                prefix = "docs"
            else:
                prefix = "chore"
            
            message = f"{prefix}: update {file_count} file(s)"
        else:
            message = f"Update {file_count} file(s)"
        
        return f"Suggested message: {message}\n\nChanges detected:\n" + "\n".join(changes)
