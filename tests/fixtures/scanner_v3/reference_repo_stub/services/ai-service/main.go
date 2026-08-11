package main

import "net/http"

func main() {
    http.HandleFunc("/ai/v1/embed", func(w http.ResponseWriter, r *http.Request) {})
}
