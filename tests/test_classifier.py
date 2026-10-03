from codekey.classifier import TaskType, classify_question


def test_classifies_wap_problem_and_python():
    result = classify_question("WAP in Python to print palindrome numbers")
    assert result.task_type is TaskType.CODING_PROBLEM


def test_other_language_requests_remain_programming_tasks():
    assert classify_question("Write a C++ program to sort an array").task_type is TaskType.CODING_PROBLEM
    assert classify_question("Write Java program to reverse a number").task_type is TaskType.CODING_PROBLEM


def test_classifies_debug_and_explanation_requests():
    assert classify_question("Why does this Python code throw IndexError?").task_type is TaskType.DEBUG
    assert classify_question("Explain what this function does").task_type is TaskType.EXPLAIN_CODE


def test_mcq_true_false_and_general_questions():
    assert classify_question("Which is correct?\nA. One\nB. Two\nC. Three\nD. Four").task_type is TaskType.MCQ
    assert classify_question("True or false: Python is interpreted?").task_type is TaskType.TRUE_FALSE
    assert classify_question("What is recursion?").task_type is TaskType.GENERAL


def test_multiple_selection_is_distinct_from_single_choice():
    question = "Select all answers that are even.\nA. 1\nB. 2\nC. 3\nD. 4"
    assert classify_question(question).task_type is TaskType.MULTI_SELECT
    question = "Choose two correct options.\nA. 1\nB. 2\nC. 3\nD. 4"
    assert classify_question(question).task_type is TaskType.MULTI_SELECT


def test_true_false_with_a_b_options_is_mcq():
    question = "Python is interpreted.\nA. True\nB. False"
    assert classify_question(question).task_type is TaskType.MCQ


def test_unlabelled_options_are_assigned_letters_by_order():
    from codekey.classifier import parse_choice_options

    question = (
        "Which of the following is a common way to print output in Python?\n"
        "echo \"Hello\"\n"
        "console.log(\"Hello\")\n"
        "print(\"Hello\")\n"
        "System.out.println(\"Hello\")"
    )
    assert classify_question(question).task_type is TaskType.MCQ
    assert parse_choice_options(question) == {
        "A": 'echo "Hello"',
        "B": 'console.log("Hello")',
        "C": 'print("Hello")',
        "D": 'System.out.println("Hello")',
    }


def test_unlabelled_bullets_preserve_option_order():
    from codekey.classifier import parse_choice_options

    question = "Choose the correct color.\n○ Red\n○ Blue\n○ Green\n○ Yellow"
    assert parse_choice_options(question) == {
        "A": "Red", "B": "Blue", "C": "Green", "D": "Yellow",
    }


def test_incomplete_unlabelled_capture_does_not_shift_option_letters():
    from codekey.classifier import parse_choice_options

    question = "Which of the following removes a list item?\ndelete()\nclear()\npop()"
    assert parse_choice_options(question) == {}
    assert classify_question(question).task_type is TaskType.GENERAL


def test_numbered_bold_unlabelled_question_keeps_fourth_option_as_d():
    from codekey.classifier import parse_choice_options

    question = (
        "**10. Which of the following removes and returns the last element of a list by default?**\n"
        "remove()\ndelete()\nclear()\npop()"
    )
    assert parse_choice_options(question)["D"] == "pop()"


def test_first_unlabelled_option_on_question_line_keeps_order():
    from codekey.classifier import parse_choice_options

    question = (
        "**10. Which of the following removes and returns the last element by default?** remove()\n"
        "delete()\nclear()\npop()"
    )
    assert parse_choice_options(question) == {
        "A": "remove()", "B": "delete()", "C": "clear()", "D": "pop()",
    }


def test_unfamiliar_question_wording_uses_four_rows_as_ordered_options():
    from codekey.classifier import parse_choice_options

    question = (
        "**14. What happens when two variables refer to the same mutable list and one variable modifies it?**\n"
        "Only that variable changes\n"
        "Both references see the modification\n"
        "Python creates a copy automatically\n"
        "An error occurs"
    )
    assert classify_question(question).task_type is TaskType.MCQ
    assert parse_choice_options(question) == {
        "A": "Only that variable changes",
        "B": "Both references see the modification",
        "C": "Python creates a copy automatically",
        "D": "An error occurs",
    }


def test_unfamiliar_question_with_first_option_on_same_line_preserves_order():
    from codekey.classifier import parse_choice_options

    question = (
        "What happens after this operation? First result\n"
        "Second result\nThird result\nFourth result"
    )
    assert parse_choice_options(question) == {
        "A": "First result", "B": "Second result", "C": "Third result", "D": "Fourth result",
    }


def test_radio_marker_after_question_is_first_option():
    from codekey.classifier import parse_choice_options

    question = "Which option is correct? ○ First\n○ Second\n○ Third\n○ Fourth"
    assert parse_choice_options(question) == {
        "A": "First", "B": "Second", "C": "Third", "D": "Fourth",
    }


def test_open_question_is_not_mcq_without_options():
    assert classify_question("Which of the following actors is best and why?").task_type is TaskType.GENERAL


def test_nonprogram_imperatives_stay_general():
    assert classify_question("Find the capital of France.").task_type is TaskType.GENERAL
    assert classify_question("Calculate 2 + 2.").task_type is TaskType.GENERAL
    assert classify_question("What is a computer program?").task_type is TaskType.GENERAL


def test_html_escaped_multichoice_format_is_mcq():
    question = (
        "**. Which keyword is used to define a function in Python?**\n"
        "A. function\\\n&#x20;B. def\\\n&#x20;C. fun\\\n&#x20;D. define\\\n&#x20;"
    )
    assert classify_question(question).task_type is TaskType.MCQ


def test_shuffled_option_labels_are_detected():
    from codekey.classifier import parse_choice_options
    question = "Which keyword defines a Python function?\nC. fun\nD. define\nA. function\nB. def"
    assert classify_question(question).task_type is TaskType.MCQ
    assert parse_choice_options(question) == {"C": "fun", "D": "define", "A": "function", "B": "def"}


def test_circled_unicode_option_letters_are_supported():
    from codekey.classifier import parse_choice_options
    question = "Choose one\nⒸ [1, 2, 3, 5]\nⒶ [1, 2, 3, 4]\nⒹ Error\nⒷ [1, 2, 3, 4, 5]"
    assert classify_question(question).task_type is TaskType.MCQ
    assert parse_choice_options(question)["B"] == "[1, 2, 3, 4, 5]"


def test_ocr_letter_on_its_own_line_is_paired_with_answer():
    from codekey.classifier import parse_choice_options
    text = "What is the output?\nA\n[1, 2, 3, 4]\nB\n[1, 2, 3, 4, 5]\nC\n[1, 2, 3, 5]\nD\nError"
    assert classify_question(text).task_type is TaskType.MCQ
    assert parse_choice_options(text)["B"] == "[1, 2, 3, 4, 5]"
