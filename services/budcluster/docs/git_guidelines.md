## 📜 Git Guidelines

Maintaining a high standard of collaboration and code quality is essential for any project. Here are the guidelines for
commit messages, pull requests (PRs), issues, code reviews, and merges to ensure consistency and clarity in your
project’s workflow.

## Table of Contents

- [Commit Messages](#-commit-messages)
- [Issues](#-issues)
- [Pull Requests](#-pull-requests)
- [Code Reviews](#-code-reviews)
- [Merges](#-merges)

## 💬 Commit Messages

Standardizing commit messages with conventions can greatly improve the readability and manageability of your project's
history. Here are some guidelines to follow:

### ✅ Combining Conventional Commits and Semantic Versioning

#### Conventional Commits [🔗](https://www.conventionalcommits.org/en/v1.0.0/#summary)

- **Overview and Benefits**: Conventional Commits provide a structured way to write commit messages that describe the
  type of change and its scope. This helps in maintaining a clear commit history and facilitates the automation of
  release processes.
- **Types and Examples**:
    - **feat**: A new feature
    - **fix**: A bug fix
    - **docs**: Documentation only changes
    - **style**: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc.)
    - **refactor**: A code change that neither fixes a bug nor adds a feature
    - **perf**: A code change that improves performance
    - **test**: Adding missing tests or correcting existing tests
    - **chore**: Changes to the build process or auxiliary tools and libraries such as documentation generation
    - **BREAKING CHANGE**: A change that breaks backward compatibility

#### Semantic Versioning [🔗](https://semver.org/)

Semantic Versioning follows a versioning pattern (major.minor.patch) that conveys the impact of changes in your
codebase.

- **Major**: Incompatible API changes
- **Minor**: Backward-compatible functionality
- **Patch**: Backward-compatible bug fixes

By using semantic versioning, you can automate version increments based on the commit messages.

#### ❓ How to Integrate Both

1. **Commit Messages**:
   Use Conventional Commits for writing your commit messages. Each commit message should follow the format:

   ```text
    <type>[optional scope]: <description>

    [optional body]
    
    [optional footer(s)]
   ```

   **Examples**:

    - Commit message with description and breaking change footer

      ```text
      feat: allow provided config object to extend other configs

      BREAKING CHANGE: `extends` key in config file is now used for extending other config files 
      ```
    - Commit message with ! to draw attention to breaking change

      ```text
      feat!: send an email to the customer when a product is shipped
      ```
    - Commit message with scope and ! to draw attention to breaking change

      ```text
      feat(api)!: send an email to the customer when a product is shipped
      ```
    - Commit message with both ! and BREAKING CHANGE footer

      ```text
      chore!: drop support for Node 6

      BREAKING CHANGE: use JavaScript features not available in Node 6.
      ```
    - Commit message with no body

      ```text
      docs: correct spelling of CHANGELOG
      ```
    - Commit message with scope

      ```text
      feat(lang): add Polish language
      ```
    - Commit message with multi-paragraph body and multiple footers

      ```text
      fix: prevent racing of requests

      Introduce a request id and a reference to latest request. Dismiss
      incoming responses other than from latest request.
        
      Remove timeouts which were used to mitigate the racing issue but are
      obsolete now.
        
      Reviewed-by: Z
      Refs: #123
      ```
2. **Version Control**:
    - Use semantic versioning principles to manage your project versions. This can be automated using tools that parse
      commit messages and increment versions accordingly.
    - Example
      tools: [semantic-release](https://github.com/semantic-release/semantic-release), [standard-version](https://github.com/conventional-changelog/standard-version)

#### 📑 Example Workflow

1. **Development**:
   Developers write commit messages using Conventional Commits format.
   Each commit message indicates the type of change and the scope, if applicable.
2. **Automated Versioning**:
   Use a tool like `semantic-release` to automatically determine the next version based on the commit messages.
   The tool parses commit messages, applies semantic versioning rules, and publishes new versions.

#### ⚙️ Example Configuration

1. **Commit Message**

   ```text
   feat(auth): add JWT authentication
   ```
   This indicates a new feature related to the authentication module.
2. **Version Increment**
    - If the commit contains a breaking change, the major version is incremented.
    - If the commit is a new feature, the minor version is incremented.
    - If the commit is a bug fix, the patch version is incremented.

#### 💡 Benefits of Using Both

- **Clarity**: Clear, structured commit messages help in understanding the history of changes.
- **Automation**: Automate the release process by generating changelogs and incrementing versions based on commit
  messages.
- **Consistency**: Maintain a consistent approach to committing and versioning across the team.

### ❌ Bad Commit Message Conventions

#### Vague Commit Messages

- **Examples and Why They Are Problematic**: Messages like "fix stuff" or "update code" are uninformative and do not
  help
  in understanding the changes made. They complicate code reviews and future maintenance.
- **How to Make Them More Specific**: Be precise and descriptive. Explain what was changed and why. Use the commit body
  to provide additional context if needed.
    - **Example**: Instead of `fix stuff`, use `fix: resolve login issue by correcting password hash algorithm`.

#### Overly Detailed Commit Messages

- **Finding the Right Balance**: Aim for clarity and conciseness. Provide enough detail to explain the change without
  overloading the reader with information.
- **Examples of Concise Yet Informative Messages**: Focus on what and why, keeping explanations brief and to the point.
    - **Example**: `feat: add caching to improve response time for user queries`.

By adhering to these conventions, you can maintain a clear and useful commit history that facilitates code reviews,
automated tooling, and future maintenance.

## 📝 Issues

Managing issues effectively ensures a smooth development process and helps in tracking bugs, feature requests, and other
tasks. Follow these guidelines when creating issues:

### Issue Format

1. **Title**: Use a clear and concise title that summarizes the issue.
    - Example: "Bug: Incorrect behavior in the health endpoint"
2. **Description**: Provide a detailed description of the issue.
    - **Steps to Reproduce**: List the steps to replicate the issue.
    - **Expected Behavior**: Describe what should happen.
    - **Actual Behavior**: Describe what actually happens.
    - **Screenshots/Logs**: Provide any relevant screenshots or log snippets.
    - **Environment**: Mention the environment where the issue was found (e.g., OS, Python version).

### Writing Issues

- **Be Clear and Concise**: Clearly describe the issue with all necessary details.
- **Use Labels**: Apply appropriate labels (e.g., bug, enhancement, documentation) to categorize the issue.
- **Provide Context**: Explain the context and the impact of the issue.

### Single vs. Multiple Issues

- **Single Issue**: Each issue should be focused on a single problem or task. Avoid listing multiple unrelated issues in
  one entry.
- **Splitting Issues**: If you identify multiple problems or tasks, split them into separate issues to keep discussions
  and resolutions focused.

### Assigning Issues

- **Self-Assignment**: If you are creating an issue for any given tasks, assign it to yourself.
- **Team Assignment**: Assign issues to appropriate team members based on their expertise.
- **Unassigned Issues**: If unsure, leave the issue unassigned and notify the team to triage and assign accordingly.

### Resolving or Closing Issues

- **Resolve**: Mark the issue as resolved when a fix is implemented and tested.
- **Close**: Close the issue once it has been reviewed, merged, and verified in the main branch.
- **Link Pull Requests**: Reference the issue in your pull request description (e.g., "Fixes #123") to automatically
  close the issue when the PR is merged.
- **Provide Updates**: Keep the issue updated with progress, comments, and any relevant changes.

**Example Bug Template**:

```markdown
### Issue Title: Bug: Incorrect behavior in the health endpoint

#### Description

- **Steps to Reproduce**:
    1. Call the `/health` endpoint.
    2. Observe the response.

#### Expected Behavior

     The endpoint should return a 200 status with the health status.

#### Actual Behavior

     The endpoint returns a 500 status with an error message.

#### Screenshots/Logs

    - [Screenshot of the error](url_to_screenshot)
    - Log snippet: `ERROR: health endpoint failed due to ...`

#### Environment

    - OS: Ubuntu 20.04
    - Python Version: 3.9.6
    - Application Version: 1.2.0
```

**Example Feature Template**:

```markdown
### Issue Title: Feature: [Brief description of the new feature]

#### Description

- **Feature Description**: Provide a detailed description of the new feature.
- **Use Case**: Explain the use case and why this feature is needed.

#### Expected Behavior

     Describe what the new feature should do and how it should behave.

#### Screenshots/Logs (Optional)

    - [Screenshot or mockup of the feature (if applicable)](url_to_screenshot)
    - Relevant logs or additional context (if applicable)

#### Environment (Optional)

    - OS: [Your Operating System]
    - Python Version: [Your Python Version]
    - Application Version: [Your Application Version]
```

### Managing Issues

- **Triage Regularly**: Regularly review and triage new issues.
- **Prioritize**: Prioritize issues based on their impact and urgency.
- **Collaborate**: Use issue comments to collaborate and discuss potential solutions.

By following these guidelines, you can ensure that your issue tracking process is organized, efficient, and effective.

## 📤 Pull Requests

Creating a well-structured Pull Request (PR) ensures that code changes are easy to review and understand. Follow these
guidelines when creating PRs:

### 🌱 Branching Strategy

- **Create a Branch for Each Issue**:
    - Each issue should have its own branch.
    - Name the branch based on the issue and the type of change, e.g., `feature/add-user-profile` or
      `bugfix/fix-login-error`.
- **Keep Branches Focused**:
    - Work on only one specific issue per branch.
    - Avoid including unrelated changes.

### ✒️ Creating a Pull Request

1. **Create a Draft PR**
    - Open a draft PR early in the development process.
    - This allows reviewers to see progress and provide early feedback.
2. **Tag Reviewers**
    - Assign relevant team members to review the PR.
    - Use GitHub’s reviewer tagging feature to notify them.
3. **Request Review Once Done**
    - Once the changes are complete and tested, mark the PR as ready for review.

### ✍️ PR Description

A comprehensive PR description helps reviewers understand the changes and the context. Include the following sections:

1. **Title**:
    - Use a clear and concise title.
    - Example: `Feature: Add User Profile Page`
2. **Linked Issues**:
    - Reference the issue(s) being addressed using keywords like Closes #123 or Resolves #456.
3. **Description**:
    - Provide a summary of the changes made.
    - Include any relevant background information or context.
4. **Methodology/Tasks Implemented**:
    - Explain the approach taken to solve the issue.
    - List the tasks to be done and check them after completion.
    - Example:
      ```markdown
      [] Implement user profile page layout.
      [] Add form for editing user information.
      [] Integrate profile picture upload functionality.
      ```
5. **Testing**:
    - Describe the testing to be performed.
    - Include steps to reproduce the testing.
    - Example:
      ```markdown
      [] Test profile page on Chrome and Firefox.
      [] Verify form validation and submission.
      ```
6. **Estimated Time**:
    - Provide an estimate of the time taken to complete the PR.
    - If the PR has more than 1 task to complete, a split per task would be preferred.
    - This helps in project planning and tracking.
7. **Screenshots/Logs**: (if applicable)
    - Include relevant screenshots or logs to demonstrate the changes.
    - Example:
     ```markdown
     ![User Profile Page Screenshot](url_to_screenshot)
     ```
8. **Additional Notes**: (optional)
    - Any additional information or caveats.

**Example PR Template**:

```markdown
### Title: Feature: Add User Profile Page

#### Linked Issues

- Closes #123

#### Description

This PR adds a user profile page where users can view and edit their personal information, such as name, email, and
profile picture.

#### Methodology/Tasks Implemented

- Implement user profile page layout. (3 hrs)
- Add form for editing user information. (3 hrs)
- Integrate profile picture upload functionality. (3 hrs)

#### Testing

- Test profile page on Chrome and Firefox. (30 min)
- Verify form validation and submission. (30 min)

#### Estimated Time

- Approximately 10 hours.

#### Screenshots/Logs

![User Profile Page Screenshot](url_to_screenshot)

#### Additional Notes

- Placeholder text added to input fields.

```

By following these guidelines, you ensure that your PRs are clear, focused, and easy to review, which helps maintain the
overall quality and efficiency of the project.

## 🔍 Code Reviews

Code reviews are essential for maintaining code quality and knowledge sharing. Follow these guidelines for code reviews:

1. **Review Thoroughly**
    - Review the entire PR, not just the changes.
    - Check for code quality, correctness, and adherence to guidelines.
2. **Provide Constructive Feedback**
    - Be respectful and constructive in your feedback.
    - Suggest improvements and ask questions to clarify the changes.
3. **Approve or Request Changes**
    - Approve the PR if it meets all requirements.
    - Request changes if there are issues that need to be addressed.

**Example feedback**:

```text
Great job on the authentication feature! I have a few suggestions:

1. Could you add a test case for the edge scenario when the user already exists?
2. The function `validate_user` could be refactored for better readability. Consider splitting it into smaller functions.

Thanks!
```

## 🔗 Merges

Merging changes into the main branch is a critical part of the development workflow. To ensure clarity, maintainability,
and ease of debugging, follow these guidelines for merging:

1. **Evaluate the Changes**: Before deciding whether to squash commits, review the branch's history. Consider the
   importance of preserving individual commit messages for future reference. Ask yourself: "If I were coding on master,
   would I commit this?" If the answer is yes, squashing is appropriate. If no, do not squash.
2. **Commit Quality**: Ensure that each commit is meaningful and provides valuable information. Avoid squashing if it
   results
   in a commit that is too large or contains too many intertwined changes.
3. **Preserve History**: For branches with a series of well-documented commits that tell the story of the development
   process,
   preserve the commit history by merging without squashing. This maintains valuable context for future developers.
4. **Clean Commits**: If the branch contains multiple small or fix-up commits that clutter the history, consider
   squashing them
   into logical units that reflect meaningful steps in the development process.
5. **Documentation**: Always write clear and concise commit messages. Even when squashing, ensure the final commit
   message
   accurately summarizes the changes made in the branch.
6. **Review Process**: Use code reviews to determine the best merge strategy. Collaborate with your team to decide
   whether
   squashing or preserving the commit history is more beneficial for the specific changes being merged.
7. **Testing**: Ensure all changes pass tests and do not break the build before merging. This is crucial for maintaining
   a
   stable main branch.
8. **Conflict Resolution**: Address and resolve any merge conflicts promptly and ensure that the final merged code is
   fully
   functional and tested.
9. **Continuous Integration**: Use CI/CD tools to automate testing and validation of merged changes, ensuring that they
   meet
   quality standards before being integrated into the main branch.

**Example Merge Commit Message**:

```text
Add user authentication feature

This commit adds the user authentication feature, including login, logout, and registration functionalities.

Fixes #123
```

By following these guidelines, you can maintain a clean and understandable commit history while ensuring that the main
branch remains stable and easy to debug.