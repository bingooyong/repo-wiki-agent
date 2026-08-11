import axios from "axios";

export async function fetchInventory() {
    return axios.get("/v1/endpoints");
}
