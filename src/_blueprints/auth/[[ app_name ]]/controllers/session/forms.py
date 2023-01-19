import proper.forms as f


class SignInForm(f.Form):
    login = f.Text()
    password = f.Password()
