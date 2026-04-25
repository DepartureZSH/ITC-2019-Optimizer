"""Official ITC2019 validator integration."""

import os
import json
from requests import post


_VALIDATE_URL = "https://www.itc2019.org/itc2019-validator"


def Validate(file: str, email: str, password: str):
    """
    Submit a solution XML to the official ITC2019 validator.

    Equivalent curl:
        curl -u email:password -H "Content-Type:text/xml;charset=UTF-8"
             -d @solution.xml https://www.itc2019.org/itc2019-validator

    Args:
        file:     path to the solution XML file
        email:    account email
        password: account password

    Returns:
        requests.Response — JSON body contains validation results.
    """
    with open(file, "rb") as f:
        response = post(
            _VALIDATE_URL,
            auth=(email, password),
            headers={"Content-Type": "text/xml;charset=UTF-8"},
            data=f.read(),
            timeout=120,
        )
    return response


def parse_official_response(response):
    """Return a best-effort structured payload from the official response."""
    content_type = response.headers.get("Content-Type", "")
    if "json" in content_type.lower():
        return response.json()
    text = response.text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def report_result(file: str, email: str = None, password: str = None, submit_report: bool = False):
    """
    Validate a solution and report the structured result to the reporting endpoint.

    Returns the parsed result dict, or None on failure.
    """
    email = email or os.environ.get("ITC2019_EMAIL")
    password = password or os.environ.get("ITC2019_PASSWORD")
    if not email or not password:
        raise ValueError("Official validation needs email/password or ITC2019_EMAIL/ITC2019_PASSWORD")

    response = Validate(file, email, password)
    print("Validate Status:", response.status_code, end="  ")

    if response.status_code != 200:
        print("Validation failed.")
        print("Response:\n", response.text)
        return None

    result = parse_official_response(response)
    if "raw" in result:
        print("Official response is not JSON.")
        print(result["raw"])
        return result

    assigned = result.get("assignedVariables", {})
    valid_str = "valid" if assigned.get("percent") == 100.0 else "invalid"

    data = {
        "instance":             result.get("instance", "error"),
        "valid":                valid_str,
        "Total cost":           result.get("totalCost",          {}).get("value", -1),
        "Time penalty":         result.get("timePenalty",        {}).get("value", -1),
        "Room penalty":         result.get("roomPenalty",        {}).get("value", -1),
        "Distribution penalty": result.get("distributionPenalty",{}).get("value", -1),
        "Student conflicts":    result.get("studentConflicts",   {}).get("value", -1),
        "Runtime":              result.get("runtime",  -1),
        "Cores":                result.get("cores",    -1),
        "Technique":            result.get("technique","error"),
    }

    if submit_report:
        report_url = os.environ.get("ITC2019_REPORT_URL")
        if not report_url:
            raise ValueError("submit_report=True needs ITC2019_REPORT_URL")
        report_token = os.environ.get("ITC2019_REPORT_TOKEN")
        headers = {"token": report_token} if report_token else {}
        resp = post(report_url, headers=headers, json=data, timeout=60)
        print("Report Status:", resp.status_code)
    return data
