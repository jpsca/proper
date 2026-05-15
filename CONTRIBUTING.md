## How to contribute to Proper

#### **Did you find a bug?**

* **Ensure the bug was not already reported** by searching on GitHub under [Issues](https://github.com/jpsca/proper/issues).

* If you're unable to find an open issue addressing the problem, [open a new one](https://github.com/jpsca/proper/issues/new). Be sure to include a **title and clear description**, as much relevant information as possible, and a **code sample** or an **executable test case** demonstrating the expected behavior that is not occurring.

#### **Did you write a patch that fixes a bug?**

* Open a new GitHub pull request with the patch.

* Ensure the PR description clearly describes the problem and solution. Include the relevant issue number if applicable.

* Before submitting, please make sure the code doesn't rises any linter error and run `uv run tox` to run the tests in all supported python versions.

#### **Did you fix whitespace, format code, or make a purely cosmetic patch?**

Changes that are cosmetic in nature and do not add anything substantial to the stability, functionality, or testability of Proper will generally not be accepted.

#### **Do you intend to add a new feature or change an existing one?**

* Look through the GitHub issues for features. Anything tagged with
"Feature request" is open to whoever wants to implement it.

#### **Do you want to contribute to the Proper documentation?**

* The project could always use more documentation, specially as blog posts, articles, and such.

### **Get Started!**

Ready to contribute? Here's how to set up the project for local development.

1.  Fork the repo on GitHub.
2.  Clone your fork locally:

```bash
git clone git@github.com:jpscaletti/proper.git
```

3.  Install your local copy into a virtualenv.

```bash
make install
```

5.  Create a branch for local development:

```bash
git switch -c name-of-your-bugfix-or-feature
```

Now you can make your changes locally.

6.  When you're done making changes, check that your changes pass all tests

```bash
make test
make lint
```

7.  Commit your changes and push your branch to GitHub:

```bash
git add .
git commit -m "Summary description of your changes."
git push origin name-of-your-bugfix-or-feature
```

8.  Submit a pull request through the GitHub website.


### **Pull Request Guidelines**

Before you submit a pull request, check that it meets these guidelines:

1.  The pull request has code, it should include tests.
2.  Run `uv run tox` and make sure that the tests pass for all supported Python versions.

### **Tips**

To run a subset of tests:

```bash
$  uv run pytest tests/the-tests-file.py
```