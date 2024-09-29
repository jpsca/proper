from proper.generators import gen_app


def test_gen_app(tmp_path):
    name = "app"
    root = tmp_path / name
    gen_app(root, force=True, _is_a_test=True)
    assert (root / name).is_dir()
    assert (root / "static").is_dir()
    assert (root / name / "config").is_dir()
    assert (root / name / "controllers").is_dir()
    assert (root / name / "forms").is_dir()
    assert (root / name / "models").is_dir()
    assert (root / name / "views").is_dir()

    assert (root / name / "app.py").exists()
    assert (root / name / "router.py").exists()


def test_gen_app_custom(tmp_path):
    name = "app"
    root = tmp_path / "project"
    gen_app(root, name=name, force=True, _is_a_test=True)
    assert (root / name).is_dir()
    assert (root / "static").is_dir()
    assert (root / name / "config").is_dir()
    assert (root / name / "controllers").is_dir()
    assert (root / name / "forms").is_dir()
    assert (root / name / "models").is_dir()
    assert (root / name / "views").is_dir()

    assert (root / name / "app.py").exists()
    assert (root / name / "router.py").exists()
