from proper.generators import gen_project


def test_gen_project(tmp_path):
    name = "app"
    root = tmp_path / name
    gen_project(root, force=True, _is_a_test=True)
    assert (root / name).is_dir()
    assert (root / "static").is_dir()
    assert (root / name / "config").is_dir()
    assert (root / name / "controllers").is_dir()
    assert (root / name / "models").is_dir()
    assert (root / name / "components").is_dir()

    assert (root / name / "app.py").exists()
    assert (root / name / "routes.py").exists()


def test_gen_project_custom(tmp_path):
    name = "app"
    root = tmp_path / "project"
    gen_project(root, name=name, force=True, _is_a_test=True)
    assert (root / name).is_dir()
    assert (root / "static").is_dir()
    assert (root / name / "config").is_dir()
    assert (root / name / "controllers").is_dir()
    assert (root / name / "models").is_dir()
    assert (root / name / "components").is_dir()

    assert (root / name / "app.py").exists()
    assert (root / name / "routes.py").exists()
