function login(credentials) {
    return { token: 'abc123' };
}

function logout(session) {
    session.destroy();
}

module.exports = { login, logout };
