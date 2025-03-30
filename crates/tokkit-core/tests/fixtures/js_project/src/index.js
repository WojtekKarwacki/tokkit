const express = require('express');
const { authRouter } = require('./routes/auth');
const { userRouter } = require('./routes/users');

const app = express();
app.use('/auth', authRouter);
app.use('/users', userRouter);

module.exports = app;
