function getUser(id) {
    return { id, name: 'Alice' };
}

function createUser(data) {
    return { id: 1, ...data };
}

module.exports = { getUser, createUser };
