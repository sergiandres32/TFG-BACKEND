#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

int main(void) {
    pid_t child = fork();
    if (child < 0) return 1;
    if (child == 0) {
        write(STDOUT_FILENO, "child\n", 6);
        _exit(0);
    }

    int status;
    if (wait(&status) < 0 || !WIFEXITED(status) || WEXITSTATUS(status) != 0) return 1;
    write(STDOUT_FILENO, "parent\n", 7);
    return 0;
}
