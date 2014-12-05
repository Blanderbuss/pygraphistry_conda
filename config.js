console.error("WARNING change graph-viz server.js to get config from ansible");

// WARNING: THIS FILE GETS OVER WRITTEN IN PRODUCTION.
// SEE ansible/roles/node-server/templates/config.j2

var _ = require('underscore');

module.exports = function() {
    var defaultOptions = {
        VIZ_LISTEN_ADDRESS: '0.0.0.0',
        VIZ_LISTEN_PORT: 10000,
        HTTP_LISTEN_ADDRESS: 'localhost',
        HTTP_LISTEN_PORT: 3000,
        MONGO_SERVER: 'localhost',
        DATABASE: 'graphistry-dev',
        HOSTNAME: 'localhost',
        DATALISTURI: 'node_modules/datasets/all.json'
    };

    var commandLineOptions = {};
    if (process.argv.length > 2) {
        try {
            commandLineOptions = JSON.parse(process.argv[2])
        } catch (err) {
            console.warn("WARNING Cannot parse command line arguments, ignoring...");
        }
    }

    var options = _.extend(defaultOptions, commandLineOptions);

    return options;
};
