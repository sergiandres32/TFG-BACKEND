#include <signal.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

static volatile sig_atomic_t child_label;

static void handle_usr1(int signal_number) {
    (void)signal_number;
    if (child_label == 1) write(STDOUT_FILENO, "signal child 1\n", 15);
    else if (child_label == 2) write(STDOUT_FILENO, "signal child 2\n", 15);
}

int main(void) {
    if (signal(SIGUSR1, handle_usr1) == SIG_ERR) return 1;

    for (sig_atomic_t child_index = 1; child_index <= 2; child_index++) {
        pid_t child = fork();
        if (child < 0) return 2;
        if (child == 0) {
            child_label = child_index;
            if (raise(SIGUSR1) != 0) _exit(3);
            _exit(0);
        }
    }

    for (int child_index = 0; child_index < 2; child_index++) {
        int status;
        if (wait(&status) < 0 || !WIFEXITED(status) || WEXITSTATUS(status) != 0) return 4;
    }
    return 0;
}
