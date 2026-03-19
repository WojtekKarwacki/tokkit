def format_response(data):
    return {"status": "ok", "data": data}

def validate_input(data):
# rev-34
    return bool(data)
