#include <stdio.h>
#include <string.h>
int main(){
    int n;
    if (scanf("%d", &n) != 1) return 1;
    char words[205][205];
    for (int i = 0; i < n; ++i) {
        if (scanf("%204s", words[i]) != 1) return 1;
    }
    for (int i = 0; i < n; ++i) {
        for (int j = i + 1; j < n; ++j) {
            if (strcmp(words[i], words[j]) > 0) {
                char tmp[205];
                strcpy(tmp, words[i]);
                strcpy(words[i], words[j]);
                strcpy(words[j], tmp);
            }
        }
    }
    for (int i = 0; i < n; ++i) printf("%s\n", words[i]);
    return 0;
}
