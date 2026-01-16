# Contributing to R.E.M.

Thank you for contributing! This guide will help you work effectively with the team.

More detailed information on the project here: [README.md](README.md)

---

## Git Workflow

### 1. Setup (First Time)

```bash
# Clone repository
git clone https://github.com/yourusername/spotify-project.git
cd spotify-project

# Install dependencies
uv sync

# Verify everything works
python scripts/playlists/spotify_cli.py --help
```

### 2. Starting New Work

```bash
# Always start from latest main
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/your-feature-name

# Examples:
# feature/add-email-reminders
# fix/csv-encoding-bug
# docs/update-quickstart
```

### 3. Making Changes

```bash
# Make your changes
# ...

# Check what changed
git status
git diff

# Stage changes
git add file1.py file2.py
# or: git add .  (add all changes)

# Commit with descriptive message
git commit -m "Add participant email validation"

# Push to GitHub
git push origin feature/your-feature-name
```

### 4. Creating Pull Request

1. Go to GitHub repository
2. Click "Compare & Pull Request" button
3. Fill in PR template:
   ```
   ## What changed
   - Added email validation for participant registration
   - Updated docs with new email format
   
   ## Why
   - Prevents invalid email addresses in system
   - Improves data quality
   
   ## Testing
   - Tested with valid/invalid emails
   - All tests pass
   ```
4. Request review if needed
5. Wait for approval
6. Click "Merge Pull Request"

### 5. After Merge

```bash
# Switch back to main
git checkout main

# Pull latest changes
git pull origin main

# Delete local feature branch
git branch -d feature/your-feature-name

# Delete remote branch (optional, GitHub does this automatically)
git push origin --delete feature/your-feature-name
```

---

## Branch Naming

| Type | Example | Use For |
|------|---------|---------|
| `feature/` | `feature/add_reminders` | New functionality |
| `fix/` | `fix/csv_encoding` | Bug fixes |
| `docs/` | `docs/update_readme` | Documentation |
| `refactor/` | `refactor/clean_generate` | Code improvements |
| `test/` | `test/add_unit_tests` | Adding tests |

---

## Commit Messages

### Good Examples
```bash
git commit -m "Add email validation for participant forms"
git commit -m "Fix CSV encoding issue with special characters"
git commit -m "Update QUICKSTART with Python 3.11 requirements"
git commit -m "Refactor playlist generation for better performance"
```

### Bad Examples
```bash
git commit -m "fix"           # Too vague
git commit -m "updates"       # Not descriptive
git commit -m "wip"           # Work in progress (commit when done)
git commit -m "asdfasdf"      # Gibberish
```

### Format
```
<type>: <short description>

Optional longer description explaining:
- Why the change was needed
- What was changed
- Any side effects
```

---

## Handling Conflicts

### When You Get a Conflict

```bash
# Pull latest main
git pull origin main

# Git marks conflicts like:
<<<<<<< HEAD
your changes here
=======
their changes here
>>>>>>> main

# Steps:
# 1. Open conflicted files
# 2. Decide which changes to keep
# 3. Remove conflict markers (<<<, ===, >>>)
# 4. Test that code works
# 5. Commit resolution

git add conflicted_file.py
git commit -m "Resolve merge conflict in generate.py"
git push origin feature/your-branch
```

### Preventing Conflicts

- Pull `main` frequently
- Keep feature branches short-lived (< 1 week)
- Communicate with team about what you're working on
- Small, focused changes instead of large rewrites

---

## Code Style

### Python
- Follow existing code style in files
- Use descriptive variable names
- Add docstrings to functions
- Keep functions focused (single responsibility)

### Example
```python
def validate_participant_email(email):
    """
    Validate participant email address format
    
    Args:
        email: Email address string
    
    Returns:
        bool: True if valid, False otherwise
    """
    # Implementation here
    pass
```

---

## Testing Your Changes

### Before Committing
```bash
# Test the main workflow
python scripts/playlists/spotify_cli.py all test_participant

# Run quick analysis
python scripts/playlists/quick_playlist_analysis.py \
  --calm test_data/calm.csv \
  --upbeat test_data/upbeat.csv \
  --id test

# Check for obvious errors
python -m py_compile scripts/playlists/spotify_cli.py
```

### If You Add New Features
- Test with real participant data (anonymized)
- Document any new command-line flags
- Update See [QUICKSTART](#QUICKSTART.md) for full workflow. if workflow changes

---

## Pull Request Checklist

Before creating PR, verify:

- [ ] Code works and has been tested
- [ ] Commit messages are descriptive
- [ ] No merge conflicts with main
- [ ] Documentation updated (if needed)
- [ ] No debugging print statements left in code
- [ ] No temporary/test files committed

---

## Getting Help

**Questions?**
- Ask in team chat/Slack
- Create GitHub Issue with `question` label
- Email: rem.study.2025@gmail.com

**Found a Bug?**
1. Check if issue already exists
2. Create new issue with:
   - What you expected to happen
   - What actually happened
   - Steps to reproduce
   - Your environment (OS, Python version)

---

## Project Roles

- **Maintainer:** Reviews and merges PRs, manages releases
- **Contributor:** Creates features, fixes bugs, improves docs
- **Participant:** Provides data (not involved in code)

---

## Quick Reference

```bash
# Daily workflow
git checkout main
git pull origin main
git checkout -b feature/my-work
# ... make changes ...
git add .
git commit -m "Descriptive message"
git push origin feature/my-work
# Create PR on GitHub

# After PR merged
git checkout main
git pull origin main
git branch -d feature/my-work
```

---

Thank you for contributing to R.E.M.! 🍎🍊🍋