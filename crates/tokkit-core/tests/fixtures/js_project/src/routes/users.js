const express = require('express');
const router = express.Router();
const { getUser, createUser } = require('../services/userService');

router.get('/', function listUsers(req, res) {
    res.json([]);
});

router.post('/', function createNewUser(req, res) {
    const user = createUser(req.body);
    res.json(user);
});

module.exports = { userRouter: router };
