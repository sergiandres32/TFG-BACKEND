#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>

/* WA: ignora argv i crea 3 fills fixos */
int main(void) {
    for (int i = 1; i <= 3; i++) {
        pid_t pid = fork();
        if (pid < 0) return 1;
        if (pid == 0) {
            printf("%d ", i);
            fflush(stdout);
            _exit(0);
        }
    }
    while (wait(NULL) > 0) {}
    printf("\n");
    return 0;
}
