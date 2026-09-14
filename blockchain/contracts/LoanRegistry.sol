// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title LoanRegistry
/// @notice Academic-prototype smart contract that provides a transparent,
/// tamper-resistant ledger of P2P micro-loan funding and repayment events.
/// This contract intentionally does NOT move real funds -- all monetary
/// values referenced (in wei-equivalent units for demonstration purposes)
/// are simulated off-chain in the FastAPI backend / MongoDB. The contract's
/// role is limited to recording immutable events for transparency, matching
/// the base paper's emphasis on trust between borrowers and lenders.
///
/// @dev v2 change: recordFunding and recordRepayment are now onlyOwner so that
/// only the deployer/backend account can write events, preventing arbitrary
/// wallets from polluting the ledger.
contract LoanRegistry {
    address public owner;

    struct FundingEvent {
        string loanId;
        string lenderRef;
        uint256 amount;
        uint256 timestamp;
    }

    struct RepaymentEvent {
        string loanId;
        string borrowerRef;
        uint256 amount;
        uint256 timestamp;
    }

    FundingEvent[]   public fundingEvents;
    RepaymentEvent[] public repaymentEvents;

    mapping(string => uint256) public totalFundedForLoan;
    mapping(string => uint256) public totalRepaidForLoan;

    event LoanFunded(string indexed loanId, string lenderRef, uint256 amount, uint256 timestamp);
    event LoanRepaid(string indexed loanId, string borrowerRef, uint256 amount, uint256 timestamp);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    modifier onlyOwner() {
        require(msg.sender == owner, "LoanRegistry: caller is not the owner");
        _;
    }

    constructor() {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    /// @notice Transfer contract ownership to a new address.
    /// @param newOwner The address to transfer ownership to.
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "LoanRegistry: new owner is the zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    /// @notice Record that a lender funded (part of) a loan.
    /// @dev onlyOwner — only the backend deployer account may write events.
    function recordFunding(
        string calldata loanId,
        string calldata lenderRef,
        uint256 amount
    ) external onlyOwner {
        require(amount > 0, "LoanRegistry: amount must be > 0");
        fundingEvents.push(FundingEvent(loanId, lenderRef, amount, block.timestamp));
        totalFundedForLoan[loanId] += amount;
        emit LoanFunded(loanId, lenderRef, amount, block.timestamp);
    }

    /// @notice Record that a borrower made a repayment on a loan.
    /// @dev onlyOwner — only the backend deployer account may write events.
    function recordRepayment(
        string calldata loanId,
        string calldata borrowerRef,
        uint256 amount
    ) external onlyOwner {
        require(amount > 0, "LoanRegistry: amount must be > 0");
        repaymentEvents.push(RepaymentEvent(loanId, borrowerRef, amount, block.timestamp));
        totalRepaidForLoan[loanId] += amount;
        emit LoanRepaid(loanId, borrowerRef, amount, block.timestamp);
    }

    function fundingEventCount() external view returns (uint256) {
        return fundingEvents.length;
    }

    function repaymentEventCount() external view returns (uint256) {
        return repaymentEvents.length;
    }
}
