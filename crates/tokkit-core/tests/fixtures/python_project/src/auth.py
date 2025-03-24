class AuthService:
    def authenticate(self, username, password):
        return self.validate(username, password)

    def validate(self, username, password):
        return username == "admin"

    def logout(self):
        pass
