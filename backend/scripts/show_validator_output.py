from app.agents.validator import format_issues_for_model, validate_files
from app.schemas.architecture import Architecture
from tests.test_validator import broken_files, contract_data


def main():
    contract = Architecture.model_validate(contract_data())
    report = validate_files(broken_files(), contract)

    print(f"Passed: {report.passed}")
    print(f"Issues found: {len(report.issues)}\n")
    print(format_issues_for_model(report))


if __name__ == "__main__":
    main()