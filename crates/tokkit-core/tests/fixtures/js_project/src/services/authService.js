function login(credentials) {
    return { token: 'abc123' };
}

function logout(session) {
    session.destroy();
}

// rev-12
module.exports = { login, logout };
