import Gui as ui
import Logic as terminal


def main():
    ui.setupGUI(terminal.COMMAND_SUGGESTIONS)
    user_path = terminal.user_data_path()

    username_entry = ui.inputText("Enter your username or type signup to create an account: ").strip()
    if username_entry.casefold() == "signup":
        username = ui.inputText("Enter your username: ").strip()
        try:
            terminal.User.loadUserData(user_path, username)
        except (FileNotFoundError, KeyError):
            pass
        except (OSError, ValueError) as error:
            ui.printOutput(f"Unable to check existing accounts: {error}")
            raise SystemExit(1) from error
        else:
            ui.printOutput("That username is already registered. Please log in or choose another.")
            raise SystemExit(1)

        password = ui.inputText("Enter your password: ")
        email = ui.inputText("Enter your email: ").strip()
        first_name = ui.inputText("Enter your first name: ").strip()
        last_name = ui.inputText("Enter your last name: ").strip()

        try:
            user = terminal.User(username, password, email, first_name, last_name)
            user.saveUserData(user_path)
        except ValueError as error:
            ui.printOutput(f"Error creating user: {error}")
            raise SystemExit(1) from error
        ui.printOutput(f"User {username} created successfully!")
    else:
        username = username_entry
        password = ui.inputText("Enter your password: ")
        try:
            user = terminal.User.loadUserData(user_path, username)
        except FileNotFoundError:
            ui.printOutput("No accounts found. Please sign up first.")
            raise SystemExit(1)
        except KeyError:
            ui.printOutput("Invalid username or password.")
            raise SystemExit(1)
        except (OSError, ValueError) as error:
            ui.printOutput(f"Unable to load account: {error}")
            raise SystemExit(1) from error

        if not user.logIn(password):
            ui.printOutput("Invalid username or password.")
            raise SystemExit(1)

    ui.enableCommandSuggestions()
    session = terminal.TermainalSession(user, password)
    ui.clear()
    ui.typeOutput(f"Welcome to TerminalPro, {user.first_name} {user.last_name}!\n")
    ui.typeOutput(f"You are logged in as: {user.username}\n")

    while True:
        user_input = ui.inputText(">")
        if user_input is None:
            continue
        output = session.runCommand(user_input)
        ui.printOutput(output)


if __name__ == "__main__":
    main()
