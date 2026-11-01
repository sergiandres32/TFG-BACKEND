#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    int input_value;
    if (argc != 3 || scanf("%d", &input_value) != 1) return 1;
    printf("%d\n", atoi(argv[1]) + atoi(argv[2]) + input_value);
    return 0;
}
