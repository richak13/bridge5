// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "./BridgeToken.sol";

contract Destination is AccessControl {
    bytes32 public constant WARDEN_ROLE = keccak256("BRIDGE_WARDEN_ROLE");
    bytes32 public constant CREATOR_ROLE = keccak256("CREATOR_ROLE");

    // Mappings for tracking underlying and wrapped tokens
    mapping(address => address) public underlying_tokens; // Maps underlying asset to BridgeToken
    mapping(address => address) public wrapped_tokens; // Maps BridgeToken to underlying asset
    address[] public tokens; // List of all created BridgeToken addresses

    // Events for tracking actions
    event Creation(address indexed underlying_token, address indexed wrapped_token);
    event Wrap(address indexed underlying_token, address indexed wrapped_token, address indexed to, uint256 amount);
    event Unwrap(address indexed underlying_token, address indexed wrapped_token, address frm, address indexed to, uint256 amount);

    constructor(address admin) {
        // Grant roles to the contract administrator
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(CREATOR_ROLE, admin);
        _grantRole(WARDEN_ROLE, admin);
    }

    // Function to create a wrapped token for the specified underlying token
    
    function createToken(
        address underlying,
        string memory name,
        string memory symbol
    ) external onlyRole(CREATOR_ROLE) returns (address) {
        require(wrapped_tokens[underlying] == address(0), "Token already registered");

        BridgeToken newToken = new BridgeToken(underlying, name, symbol, address(this));
        wrapped_tokens[underlying] = address(newToken);
        underlying_tokens[address(newToken)] = underlying;

        emit Creation(underlying, address(newToken));
        return address(newToken);
    }

    function wrap(
        address underlying,
        address recipient,
        uint256 amount
    ) external onlyRole(WARDEN_ROLE) {
        address bridgeToken = wrapped_tokens[underlying];
        require(bridgeToken != address(0), "Token not registered");

        BridgeToken(bridgeToken).mint(recipient, amount);
        emit Wrap(underlying, bridgeToken, recipient, amount);
    }

    function unwrap(
        address bridgeToken,
        address recipient,
        uint256 amount
    ) external {
        address underlying = underlying_tokens[bridgeToken];
        require(underlying != address(0), "Token not registered");
        require(BridgeToken(bridgeToken).balanceOf(msg.sender) >= amount, "Insufficient balance");

        BridgeToken(bridgeToken).burnFrom(msg.sender, amount);
        emit Unwrap(underlying, bridgeToken, msg.sender, recipient, amount);
    }
}
