class UserService:
    def get_user(self, user_id):
        return {"id": user_id, "name": "Alice"}

    def create_user(self, data):
        return {"id": 1, **data}
