local plugin = {
    id          = "tiktok_osint_pro",
    name        = "TikTok OSINT",
    description = "Advanced TikTok OSINT: Profile scraping & Hashtag video search with Graph visualization.",
    author      = "Laitoxx Community",
    version     = "1.0",
    type        = "search",

    config_schema = {
        { key = "timeout",      label = "Request Timeout (sec)", type = "number",  default = 15 },
        { key = "max_results",  label = "Max Tag Results",       type = "number",  default = 10 },
        { key = "generate_graph", label = "Auto-generate Graph",  type = "boolean", default = true }
    }
}

local user_agents = {
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
}

-- Safe table navigator to prevent "index a nil value"
local function get_path(t, ...)
    local keys = {...}
    local curr = t
    for _, key in ipairs(keys) do
        if type(curr) ~= "table" then return nil end
        curr = curr[key]
    end
    return curr
end

-- Mode: Profile Search Logic
local function handle_profile(body, username)
    -- Try different script tags where TikTok hides JSON data
    local json_str = string.match(body, '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" [^>]*>(.-)</script>')
    if not json_str then json_str = string.match(body, '<script id="SIGI_STATE" [^>]*>(.-)</script>') end
    if not json_str then json_str = string.match(body, '<script id="__NEXT_DATA__" [^>]*>(.-)</script>') end
    
    if not json_str then 
        return nil, "Could not find data structure. The user might not exist or TikTok is blocking the request." 
    end

    local full_data = host:json_decode(json_str)
    if not full_data then 
        return nil, "Failed to parse profile JSON." 
    end

    local user_info = nil
    local stats = nil

    -- Safe search through common paths
    local detail = get_path(full_data, "__DEFAULT_SCOPE__", "webapp.user-detail")
    if detail and detail.userInfo then
        user_info = detail.userInfo.user
        stats = detail.userInfo.stats
    elseif full_data.props and full_data.props.pageProps and full_data.props.pageProps.userInfo then
        -- Path for __NEXT_DATA__
        user_info = full_data.props.pageProps.userInfo.user
        stats = full_data.props.pageProps.userInfo.stats
    elseif full_data.UserModule then
        -- Path for older layouts
        for _, v in pairs(full_data.UserModule.users or {}) do user_info = v break end
        for _, v in pairs(full_data.UserModule.stats or {}) do stats = v break end
    end

    if not user_info then 
        return nil, "User data is missing. The account might be private, banned, or the username is incorrect." 
    end

    local uid = tostring(user_info.uniqueId or username)
    local nick = tostring(user_info.nickname or "N/A")
    local bio = tostring(user_info.signature or "")
    local followers = tostring(stats and stats.followerCount or 0)
    local likes = tostring(stats and stats.heartCount or 0)

    local lines = {
        "╔═══════════════════════════════════════════════════════════╗",
        "║                TIKTOK PROFILE REPORT                      ║",
        "╚═══════════════════════════════════════════════════════════╝",
        "Username:  @" .. uid,
        "Nickname:  " .. nick,
        "Bio:       " .. (bio ~= "" and bio or "[No bio]"),
        "Followers: " .. followers,
        "Likes:     " .. likes,
        "",
        "--- OSINT Links ---",
        "Exolyt:    https://exolyt.com/user/" .. uid,
        "Urlebird:  https://urlebird.com/user/" .. uid .. "/"
    }

    if host:get_config("generate_graph") then
        local gid = host:graph_create("TikTok Profile: " .. uid, "TD")
        local m = host:graph_add_node(gid, "@" .. uid, "Person", "circle", "fill:#ff0050,color:#fff")
        if bio ~= "" then 
            local b = host:graph_add_node(gid, "Bio", "Document", "round", "fill:#eee", bio)
            host:graph_add_edge(gid, m, b, "info")
        end
        host:graph_save(gid, "tiktok_user_" .. uid .. ".graph.json")
    end

    return table.concat(lines, "\n")
end

-- Mode: Hashtag Search Logic
local function handle_tag(body, tag)
    local json_str = string.match(body, '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" [^>]*>(.-)</script>')
    if not json_str then json_str = string.match(body, '<script id="__NEXT_DATA__" [^>]*>(.-)</script>') end
    
    if not json_str then return nil, "Tag data not found." end
    local full_data = host:json_decode(json_str)
    if not full_data then return nil, "JSON Decode Error" end

    local items = {}
    local detail = get_path(full_data, "__DEFAULT_SCOPE__", "webapp.challenge-detail")
    if detail then
        items = detail.itemList or {}
    elseif get_path(full_data, "props", "pageProps", "items") then
        items = full_data.props.pageProps.items
    end

    if not items or #items == 0 then
        return "No recent videos found for tag: #" .. tag
    end

    local max_v = host:get_config("max_results") or 10
    local lines = {
        "╔═══════════════════════════════════════════════════════════╗",
        "║                TIKTOK TAG SEARCH RESULTS                  ║",
        "╚═══════════════════════════════════════════════════════════╝",
        "Tag: #" .. tag,
        "Found: " .. tostring(#items) .. " videos",
        ""
    }

    local gid = nil
    local tag_node = nil
    if host:get_config("generate_graph") then
        gid = host:graph_create("TikTok Tag: #" .. tag, "LR")
        tag_node = host:graph_add_node(gid, "#" .. tag, "Custom", "diamond", "fill:#00f2ea,color:#000")
    end

    for i = 1, math.min(#items, max_v) do
        local item = items[i]
        local author = get_path(item, "author", "uniqueId") or "unknown"
        local v_id = tostring(item.id or i)
        local v_url = "https://www.tiktok.com/@" .. author .. "/video/" .. v_id
        local u_url = "https://www.tiktok.com/@" .. author
        local desc = tostring(item.desc or "[No description]")
        local d_count = tostring(get_path(item, "stats", "diggCount") or 0)
        
        local short_desc = string.sub(desc, 1, 50)
        if string.len(desc) > 50 then short_desc = short_desc .. "..." end

        table.insert(lines, "[" .. i .. "] Author: @" .. author)
        table.insert(lines, "    Profile: " .. u_url)
        table.insert(lines, "    Video:   " .. v_url)
        table.insert(lines, "    Desc:    " .. short_desc)
        table.insert(lines, "    Likes:   " .. d_count)
        table.insert(lines, "-------------------------------------------------------------")

        if gid then
            local u_node = host:graph_add_node(gid, "@" .. author, "Person", "rect")
            local v_node = host:graph_add_node(gid, "Video_" .. v_id, "Video", "round", "fill:#ff0050,color:#fff", desc)
            host:graph_add_edge(gid, tag_node, v_node, "tagged")
            host:graph_add_edge(gid, u_node, v_node, "posted")
        end
    end

    if gid then host:graph_save(gid, "tiktok_tag_" .. tag .. ".graph.json") end
    return table.concat(lines, "\n")
end

-- Main Handler Function
function plugin.search(query, options)
    if not query or query == "" then return nil, "Enter @username or #tag." end

    local first_char = string.sub(query, 1, 1)
    local is_tag = (first_char == "#")
    local clean_query = query
    if first_char == "@" or first_char == "#" then clean_query = string.sub(query, 2) end

    local timeout = host:get_config("timeout") or 15
    local ua = user_agents[math.random(#user_agents)]
    local url = is_tag and ("https://www.tiktok.com/tag/" .. host:url_encode(clean_query)) 
                        or ("https://www.tiktok.com/@" .. host:url_encode(clean_query))

    host:print("[*] Fetching: " .. url)
    local body, err = host:http_get(url, timeout, { ["User-Agent"] = ua })
    if not body then return nil, "Request failed: " .. tostring(err or "check connection") end

    if is_tag then
        return handle_tag(body, clean_query)
    else
        return handle_profile(body, clean_query)
    end
end

return plugin