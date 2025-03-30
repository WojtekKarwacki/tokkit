const express = require('express');
const router = express.Router();
const { login, logout } = require('../services/authService');

router.post('/login', function handleLogin(req, res) {
    const result = login(req.body);
    res.json(result);
});

router.post('/logout', function handleLogout(req, res) {
    logout(req.session);
    res.json({ ok: true });
});

module.exports = { authRouter: router };
