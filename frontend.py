import streamlit as st
from mongo import arxiv_db
from datetime import datetime

st.set_page_config(page_title="Arxiv", page_icon="./icon.jpg")

# Initialize session state for the last marked paper
if 'last_marked_paper' not in st.session_state:
    st.session_state.last_marked_paper = None

def getDates():
    unreadOnly = st.selectbox(
        "未读/已读/Star/所有",
        options=[
            dict(value={"$exists": False}, label="未读"),  # UnRead Only
            dict(value={"$exists": True}, label="已读"),  # Already Read
            dict(value="Star", label="标星⭐️"),  # Starred
            dict(value=False, label="All")  # All
        ],
        format_func=lambda x: x["label"],
        index=0)["value"]
    if unreadOnly:
        num = arxiv_db.count_documents({"Read": unreadOnly})
        dates = sorted(arxiv_db.find({"Read": unreadOnly}).distinct("email_date"), reverse=False)
    else:
        num = arxiv_db.count_documents({})
        dates = sorted(arxiv_db.find({}).distinct("email_date"), reverse=False)
    st.markdown(f"**{num}** Papers in List")
    if not dates:
        st.warning("No papers found for the selected criteria.")
        return None, unreadOnly
    
    if len(dates) == 1:
        dates.append(dates[0])
    
    k = st.select_slider("选择日期", options=dates, value=dates[-1] if dates else None)
    # k = st.date_input("选择日期", datetime.today())
    # k = k.strftime("%Y-%m-%d")
    return k, unreadOnly

def MarkRead(paper_id):
    arxiv_db.update_one(dict(_id=paper_id), {"$set": {"Read": "Read"}})
    st.session_state.last_marked_paper = paper_id

def MarkStar(paper_id):
    arxiv_db.update_one(dict(_id=paper_id), {"$set": {"Read": "Star"}})
    st.session_state.last_marked_paper = paper_id

def getPapers(date, unreadOnly, page_number, page_size):
    query = dict(email_date=date)
    if unreadOnly:
        query["Read"] = unreadOnly
    
    total_papers = arxiv_db.count_documents(query)
    total_pages = (total_papers + page_size - 1) // page_size
    
    st.markdown(f"Page {page_number + 1} of {total_pages}")
    
    skip = page_number * page_size
    limit = page_size
    
    papers = list(arxiv_db.find(query).skip(skip).limit(limit))
    
    for paper in papers:
        raw_title = paper["title"]
        if "Read" in paper:
            if paper["Read"] == "Star":
                paper["title"] = "\\[标星⭐️\\] " + f"*{paper['title']}*"
            else:
                paper["title"] = "\\[已读\\] " + f"*{paper['title']}*"
        else:
            paper["title"] = "\\[未读\\] " + f"*{paper['title']}*"
        
        expand = False
        if st.session_state.last_marked_paper == paper["_id"]:
            expand = True
            st.session_state.last_marked_paper = None  # Reset the session state
        
        with st.expander(paper["title"], expanded=expand):
            paper_id = paper["_id"]
            l, r = st.columns(2)
            l.button(
                "Mark → 已读",
                on_click=MarkRead,
                key=paper["link"] + "read",
                use_container_width=True,
                kwargs=dict(paper_id=paper_id),
                disabled=("Read" in paper)
            )
            r.button(
                "Mark → 标星⭐️",
                on_click=MarkStar,
                key=paper["link"] + "star",
                use_container_width=True,
                kwargs=dict(paper_id=paper_id),
                disabled=("Read" in paper and paper["Read"] == "Good")
            )
            st.markdown(f"### {raw_title}")
            st.markdown("###### [View in arXiv]({})".format(paper["link"].replace("abs", "pdf") + ".pdf"))
            for key, value in sorted(list(paper.items()), key=lambda x: x[0]):
                if key in ["_id", "link", "email_date", "title", "cs", "Read"]:
                    continue
                st.markdown(f"###### {key}")
                if key == "abstract":
                    value = value.replace(". ", ".\n\n")
                st.markdown(
                    value if value is not str else bionic_reading(value),
                    unsafe_allow_html=True)
            if "cs" in paper:
                st.markdown(f"###### tags(under cs)")
                st.markdown(', '.join(list(paper["cs"].keys())))

date, unreadOnly = getDates()

# Pagination settings
page_size = 10  # Number of papers per page
page_number = st.number_input("Page Number", min_value=1, value=1, step=1) - 1

getPapers(date, unreadOnly, page_number, page_size)