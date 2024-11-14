from proper.generators import gen_app


def test_gen_app(tmp_path):
    name = "myapp"
    root = tmp_path / name
    gen_app(root, force=True, _is_a_test=True)
    assert (root / "static").is_dir()
    assert (root / "config").is_dir()
    assert (root / "app" / "controllers").is_dir()
    assert (root / "app" / "forms").is_dir()
    assert (root / "app" / "models").is_dir()
    assert (root / "app" / "views").is_dir()

    assert (root / "app" / "main.py").exists()
    assert (root / "app" / "router.py").exists()


def test_gen_app_custom(tmp_path):
    name = "myapp"
    root = tmp_path / "project"
    gen_app(root, name=name, force=True, _is_a_test=True)
    assert (root / "static").is_dir()
    assert (root / "config").is_dir()
    assert (root / "app" / "controllers").is_dir()
    assert (root / "app" / "forms").is_dir()
    assert (root / "app" / "models").is_dir()
    assert (root / "app" / "views").is_dir()

    assert (root / "app" / "main.py").exists()
    assert (root / "app" / "router.py").exists()
