if st.button("🔍 Scan for Viral Broncos & Nuggets Bangers", use_container_width=True):
    with st.spinner("Scanning for absolute viral bangers (30+ replies, 100+ likes, 15+ RTs)..."):
        # Search Broncos
        broncos_keywords = ["Denver Broncos", "Sean Payton", "Bo Nix", "Broncos"]
        broncos_tweets = search_viral_tweets(broncos_keywords)
        
        # Search Nuggets
        nuggets_keywords = ["Denver Nuggets", "Nikola Jokic", "Nuggets"]
        nuggets_tweets = search_viral_tweets(nuggets_keywords)
        
        # Get top 10 Broncos and top 5 Nuggets
        top_broncos = broncos_tweets[:10]
        top_nuggets = nuggets_tweets[:5]
        
        all_tweets = top_broncos + top_nuggets
        
        if all_tweets:
            st.success(f"✅ Found {len(top_broncos)} Broncos + {len(top_nuggets)} Nuggets viral bangers!")
            
            # Show TOP 3 Broncos picks first
            st.markdown("### ⭐ TOP 3 BRONCOS PICKS")
            for i, tweet in enumerate(top_broncos[:3]):
                tweet_url = f"https://twitter.com/{tweet['author']}/status/{tweet['id']}"
                
                st.markdown(f"""
                <div class="tweet-card top-pick">
                    <span class="top-pick-badge">⭐ TOP PICK #{i+1}</span>
                    <div class="tweet-header">
                        <span class="priority-badge {tweet['priority']['color']}">{tweet['priority']['label']}</span>
                        <strong>{tweet['author_name']}</strong> @{tweet['author']}
                    </div>
                    <div class="tweet-text">{tweet['text']}</div>
                    <div class="tweet-metrics">
                        <span class="metric-high">💬 {tweet['replies']} replies</span>
                        <span class="metric-high">🔄 {tweet['retweets']} RTs</span>
                        <span class="metric-high">❤️ {tweet['likes']} likes</span>
                    </div>
                    <a href="{tweet_url}" target="_blank" style="color: #1d9bf0; text-decoration: none;">🔗 View on Twitter →</a>
                </div>
                """, unsafe_allow_html=True)
                
                with st.spinner("Generating rewrites..."):
                    rewrites = generate_rewrites(tweet['text'])
                
                st.markdown("**✍️ Your Rewrites:**")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"<div class='rewrite-preview'><strong>Default:</strong><br>{rewrites['Default']}</div>", unsafe_allow_html=True)
                    if st.button(f"📋 Copy Default", key=f"copy_default_{i}"):
                        st.code(rewrites['Default'], language=None)
                    
                    st.markdown(f"<div class='rewrite-preview'><strong>Analytical:</strong><br>{rewrites['Analytical']}</div>", unsafe_allow_html=True)
                    if st.button(f"📋 Copy Analytical", key=f"copy_analytical_{i}"):
                        st.code(rewrites['Analytical'], language=None)
                
                with col2:
                    st.markdown(f"<div class='rewrite-preview'><strong>Controversial:</strong><br>{rewrites['Controversial']}</div>", unsafe_allow_html=True)
                    if st.button(f"📋 Copy Controversial", key=f"copy_controversial_{i}"):
                        st.code(rewrites['Controversial'], language=None)
                    
                    st.markdown(f"<div class='rewrite-preview'><strong>Personal:</strong><br>{rewrites['Personal']}</div>", unsafe_allow_html=True)
                    if st.button(f"📋 Copy Personal", key=f"copy_personal_{i}"):
                        st.code(rewrites['Personal'], language=None)
                
                st.markdown("---")
            
            # Show remaining 7 Broncos tweets
            if len(top_broncos) > 3:
                st.markdown("### 🏈 Other Broncos Tweets")
                for i, tweet in enumerate(top_broncos[3:], start=3):
                    tweet_url = f"https://twitter.com/{tweet['author']}/status/{tweet['id']}"
                    
                    st.markdown(f"""
                    <div class="tweet-card">
                        <div class="tweet-header">
                            <span class="priority-badge {tweet['priority']['color']}">{tweet['priority']['label']}</span>
                            <strong>{tweet['author_name']}</strong> @{tweet['author']}
                        </div>
                        <div class="tweet-text">{tweet['text']}</div>
                        <div class="tweet-metrics">
                            <span class="metric-high">💬 {tweet['replies']} replies</span>
                            <span>🔄 {tweet['retweets']} RTs</span>
                            <span>❤️ {tweet['likes']} likes</span>
                        </div>
                        <a href="{tweet_url}" target="_blank" style="color: #1d9bf0; text-decoration: none;">🔗 View on Twitter →</a>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.spinner("Generating rewrites..."):
                        rewrites = generate_rewrites(tweet['text'])
                    
                    st.markdown("**✍️ Your Rewrites:**")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"<div class='rewrite-preview'><strong>Default:</strong><br>{rewrites['Default']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy Default", key=f"copy_default_b{i}"):
                            st.code(rewrites['Default'], language=None)
                        
                        st.markdown(f"<div class='rewrite-preview'><strong>Analytical:</strong><br>{rewrites['Analytical']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy Analytical", key=f"copy_analytical_b{i}"):
                            st.code(rewrites['Analytical'], language=None)
                    
                    with col2:
                        st.markdown(f"<div class='rewrite-preview'><strong>Controversial:</strong><br>{rewrites['Controversial']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy Controversial", key=f"copy_controversial_b{i}"):
                            st.code(rewrites['Controversial'], language=None)
                        
                        st.markdown(f"<div class='rewrite-preview'><strong>Personal:</strong><br>{rewrites['Personal']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy Personal", key=f"copy_personal_b{i}"):
                            st.code(rewrites['Personal'], language=None)
                    
                    st.markdown("---")
            
            # Show 5 Nuggets tweets
            if top_nuggets:
                st.markdown("### 🏀 Denver Nuggets Tweets")
                for i, tweet in enumerate(top_nuggets):
                    tweet_url = f"https://twitter.com/{tweet['author']}/status/{tweet['id']}"
                    
                    st.markdown(f"""
                    <div class="tweet-card">
                        <div class="tweet-header">
                            <span class="priority-badge" style="background-color: #fdb927; color: #00285e;">🏀 NUGGETS</span>
                            <strong>{tweet['author_name']}</strong> @{tweet['author']}
                        </div>
                        <div class="tweet-text">{tweet['text']}</div>
                        <div class="tweet-metrics">
                            <span class="metric-high">💬 {tweet['replies']} replies</span>
                            <span>🔄 {tweet['retweets']} RTs</span>
                            <span>❤️ {tweet['likes']} likes</span>
                        </div>
                        <a href="{tweet_url}" target="_blank" style="color: #1d9bf0; text-decoration: none;">🔗 View on Twitter →</a>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.spinner("Generating rewrites..."):
                        rewrites = generate_rewrites(tweet['text'])
                    
                    st.markdown("**✍️ Your Rewrites:**")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"<div class='rewrite-preview'><strong>Default:</strong><br>{rewrites['Default']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy Default", key=f"copy_default_n{i}"):
                            st.code(rewrites['Default'], language=None)
                        
                        st.markdown(f"<div class='rewrite-preview'><strong>Analytical:</strong><br>{rewrites['Analytical']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy Analytical", key=f"copy_analytical_n{i}"):
                            st.code(rewrites['Analytical'], language=None)
                    
                    with col2:
                        st.markdown(f"<div class='rewrite-preview'><strong>Controversial:</strong><br>{rewrites['Controversial']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy Controversial", key=f"copy_controversial_n{i}"):
                            st.code(rewrites['Controversial'], language=None)
                        
                        st.markdown(f"<div class='rewrite-preview'><strong>Personal:</strong><br>{rewrites['Personal']}</div>", unsafe_allow_html=True)
                        if st.button(f"📋 Copy Personal", key=f"copy_personal_n{i}"):
                            st.code(rewrites['Personal'], language=None)
                    
                    st.markdown("---")
        else:
            st.warning("No viral bangers found matching your criteria (30+ replies, 100+ likes, 15+ RTs). Try again in a few hours!")
