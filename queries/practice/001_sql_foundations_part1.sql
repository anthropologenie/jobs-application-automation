-- ============================================================
-- Sprint 1 : SQL Foundations (Part 1)
-- Questions 1-5
-- Date: 2026-08-03
-- ============================================================

---------------------------------------------------------------
-- Question 1
---------------------------------------------------------------

INSERT INTO practice_sessions (
    source,
    domain,
    platform,
    question_text,
    my_solution,
    correct_solution,
    is_correct,
    difficulty,
    time_spent_minutes,
    error_made,
    lesson_learned,
    concepts_used,
    notes
)
VALUES (
    'Practice',
    'SQL',
    'DBeaver',

    'Return employees with salary greater than 60000 ordered by salary descending.',

'SELECT emp.name
FROM employee emp
WHERE salary > 60000
ORDER BY salary DESC;',

'SELECT name, salary
FROM employee
WHERE salary > 60000
ORDER BY salary DESC;',

1,

'Easy',

NULL,

'Selected only employee name instead of including salary for easier verification.',

'Understand the requirement first. Include useful output columns when appropriate.',

'SELECT,WHERE,ORDER BY',

'Reviewed with ChatGPT. Solution correct.'
);

---------------------------------------------------------------
-- Question 2
---------------------------------------------------------------

INSERT INTO practice_sessions (
source,
domain,
platform,
question_text,
my_solution,
correct_solution,
is_correct,
difficulty,
time_spent_minutes,
error_made,
lesson_learned,
concepts_used,
notes
)
VALUES (
'Practice',
'SQL',
'DBeaver',

'Return department_id and number of employees.',

'SELECT emp.department_id,
COUNT(*) AS number_of_employees
FROM employee emp
GROUP BY emp.department_id;',

'SELECT department_id,
COUNT(*)
FROM employee
GROUP BY department_id;',

1,

'Easy',

NULL,

NULL,

'COUNT(*) counts rows and is preferred for employee count.',

'GROUP BY,COUNT',

'Reviewed.'
);

---------------------------------------------------------------
-- Question 3
---------------------------------------------------------------

INSERT INTO practice_sessions (
source,
domain,
platform,
question_text,
my_solution,
correct_solution,
is_correct,
difficulty,
time_spent_minutes,
error_made,
lesson_learned,
concepts_used,
notes
)
VALUES (
'Practice',
'SQL',
'DBeaver',

'Return departments having more than five employees.',

'SELECT emp.department_id,
dept.department_name
FROM employee emp
JOIN department dept
ON emp.department_id=dept.department_id
GROUP BY emp.department_id,
dept.department_name
HAVING COUNT(emp.emp_id)>5;',

'SELECT department_id
FROM employee
GROUP BY department_id
HAVING COUNT(*)>5;',

1,

'Medium',

NULL,

'Used an unnecessary JOIN.',

'Only join tables when additional information is required.',

'GROUP BY,HAVING,JOIN',

'Logic correct.'
);

---------------------------------------------------------------
-- Question 4
---------------------------------------------------------------

INSERT INTO practice_sessions (
source,
domain,
platform,
question_text,
my_solution,
correct_solution,
is_correct,
difficulty,
time_spent_minutes,
error_made,
lesson_learned,
concepts_used,
notes
)
VALUES (
'Practice',
'SQL',
'DBeaver',

'Categorize salaries into High, Medium and Low using CASE.',

'SELECT name,
salary,
CASE
WHEN salary<60000 THEN ''low''
WHEN salary BETWEEN 60000 AND 99999 THEN ''medium''
WHEN salary>=100000 THEN ''high''
END AS salary_band
FROM employee;',

'SELECT name,
salary,
CASE
WHEN salary>=100000 THEN ''High''
WHEN salary>=60000 THEN ''Medium''
ELSE ''Low''
END AS salary_band
FROM employee;',

1,

'Medium',

NULL,

'Initially wrote table name as employees instead of employee.',

'CASE conditions can often be simplified by ordering from highest to lowest.',

'CASE',

'Minor typo only.'
);

---------------------------------------------------------------
-- Question 5
---------------------------------------------------------------

INSERT INTO practice_sessions (
source,
domain,
platform,
question_text,
my_solution,
correct_solution,
is_correct,
difficulty,
time_spent_minutes,
error_made,
lesson_learned,
concepts_used,
notes
)
VALUES (
'Practice',
'SQL',
'DBeaver',

'Swap Male and Female values using UPDATE CASE.',

'UPDATE employee
SET gender =
CASE
WHEN LOWER(gender)=''male'' THEN ''female''
WHEN LOWER(gender)=''female'' THEN ''male''
END;',

'UPDATE employee
SET gender =
CASE
WHEN LOWER(gender)=''male'' THEN ''Female''
WHEN LOWER(gender)=''female'' THEN ''Male''
ELSE gender
END;',

1,

'Medium',

NULL,

'Forgot ELSE clause for unexpected values.',

'Always preserve values you do not intend to modify.',

'UPDATE,CASE',

'Handled case-insensitive comparison correctly.'
);
