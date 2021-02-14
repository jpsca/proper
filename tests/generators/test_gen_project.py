from proper.generators import gen_project


def test_gen_project(dst):
    name = "app"
    root = dst / name
    gen_project(root, force=True, _dependencies=False)
    assert (root / name).is_dir()
    assert (root / "static").is_dir()
    assert (root / name / "config").is_dir()
    assert (root / name / "controllers").is_dir()
    assert (root / name / "models").is_dir()
    assert (root / name / "templates").is_dir()

    assert (root / name / "app.py").exists()
    assert (root / name / "main.py").exists()
    assert (root / name / "routes.py").exists()


def test_gen_project_custom(dst):
    name = "app"
    root = dst / "project"
    gen_project(root, name=name, force=True, _dependencies=False)
    assert (root / name).is_dir()
    assert (root / "static").is_dir()
    assert (root / name / "config").is_dir()
    assert (root / name / "controllers").is_dir()
    assert (root / name / "models").is_dir()
    assert (root / name / "templates").is_dir()

    assert (root / name / "app.py").exists()
    assert (root / name / "main.py").exists()
    assert (root / name / "routes.py").exists()
