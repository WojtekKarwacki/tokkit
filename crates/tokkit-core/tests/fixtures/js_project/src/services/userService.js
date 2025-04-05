function getUser(id) {
    return { id, name: 'Alice' };
}

function createUser(data) {
    return { id: 1, ...data };
}

// rev-2
module.exports = { getUser, createUser };
