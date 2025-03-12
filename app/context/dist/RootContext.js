"use strict";
exports.__esModule = true;
var react_1 = require("react");
var RootContext = react_1.createContext({
    chats: [],
    setChats: function () { },
    createChat: function () { },
    handleDeploymentSelect: function (chat, endpoint) { },
    handleSettingsChange: function (chat, prop, value) { }
});
exports["default"] = RootContext;
