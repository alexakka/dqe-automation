*** Settings ***
Library           SeleniumLibrary
Library           helper.py
Test Teardown     Close All Browsers

*** Variables ***
${REPORT_FILE}      ${CURDIR}/../data/generated_report/report.html
${PARQUET_FOLDER}   ${CURDIR}/../data/parquet_data/facility_type_avg_time_spent_per_visit_date
${FILTER_DATE}      2026-09-27
${BROWSER}          headlesschrome
${TABLE_LOCATOR}    css:g.table
${BROWSER_OPTIONS}    add_argument("--window-size=1400,1000")

*** Test Cases ***
HTML Table Should Match Parquet Data
    Open Browser    file://${REPORT_FILE}    ${BROWSER}    options=${BROWSER_OPTIONS}
    Wait Until Element Is Visible    ${TABLE_LOCATOR}    timeout=10s
    ${table}=    Get WebElement    ${TABLE_LOCATOR}
    ${html_df}=    Read Html Table    ${table}
    ${parquet_df}=    Read Parquet Data    ${PARQUET_FOLDER}    ${FILTER_DATE}
    ${diff}=    Compare Dataframes    ${html_df}    ${parquet_df}
    Should Be True    ${diff.empty}    Table and Parquet data differ:\n${diff}



