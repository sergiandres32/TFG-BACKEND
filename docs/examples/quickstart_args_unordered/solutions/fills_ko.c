#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>

/* WA: nomes 3 fills, falta la linia "fill 4" */
int main(void) {
    for (int i = 1; i <= 3; i++) {
        pid_t pid = fork();
        if (pid < 0) return 1;
        if (pid == 0) {
            printf("fill %d\n", i);
            fflush(stdout);
            _exit(0);
        }
    }
    while (wait(NULL) > 0) {}
    return 0;
}
