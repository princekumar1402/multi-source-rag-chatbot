import uuid
from typing import List
from backend.app.schemas.document import DocumentChunk, ChunkMetadata, SourceType

def get_evaluation_corpus() -> List[DocumentChunk]:
    """
    Returns a controlled, deterministic multi-source evaluation corpus with
    ground truth documents across all 8 supported source types plus realistic distractors.
    """
    workspace_id = "eval-workspace"
    corpus: List[DocumentChunk] = []

    # ==========================================
    # 1. PDF - Operating Systems Manual (doc-pdf-01)
    # ==========================================
    doc_id_pdf = "doc-pdf-eval-01"
    corpus.append(DocumentChunk(
        chunk_id="chunk-pdf-p24-1",
        content="In operating systems, a deadlock is a situation where a set of processes are blocked because each process is holding a resource and waiting for another resource. The four necessary conditions for deadlock (Coffman conditions) are: 1. Mutual Exclusion: At least one resource must be held in a non-shareable mode. 2. Hold and Wait: A process must be holding at least one resource and waiting to acquire additional resources. 3. No Preemption: Resources cannot be preempted; they can only be released voluntarily by the process holding them. 4. Circular Wait: A closed chain of processes exists such that each process holds at least one resource needed by the next process.",
        metadata=ChunkMetadata(
            document_id=doc_id_pdf,
            workspace_id=workspace_id,
            source_type=SourceType.PDF,
            source_name="Operating_Systems_Notes.pdf",
            file_name="Operating_Systems_Notes.pdf",
            page_number=24,
            page_index=23,
            section_title="Deadlocks and Coffman Conditions"
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-pdf-p23-1",
        content="CPU scheduling deals with the problem of deciding which of the processes in the ready queue is to be allocated the CPU. Scheduling algorithms include First-Come First-Served (FCFS), Shortest Job First (SJF), Round Robin (RR), and Multilevel Feedback Queue. Round Robin uses a fixed time quantum; if a process does not complete within its time slice, it is preempted and placed at the tail of the ready queue.",
        metadata=ChunkMetadata(
            document_id=doc_id_pdf,
            workspace_id=workspace_id,
            source_type=SourceType.PDF,
            source_name="Operating_Systems_Notes.pdf",
            file_name="Operating_Systems_Notes.pdf",
            page_number=23,
            page_index=22,
            section_title="CPU Scheduling Algorithms"
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-pdf-p31-1",
        content="Virtual memory paging separates logical address spaces from physical memory. The operating system maintains a page table mapping virtual pages to physical page frames. When a process accesses a page not present in physical RAM, the CPU hardware generates a page fault interrupt, prompting the kernel to load the missing page from swap storage.",
        metadata=ChunkMetadata(
            document_id=doc_id_pdf,
            workspace_id=workspace_id,
            source_type=SourceType.PDF,
            source_name="Operating_Systems_Notes.pdf",
            file_name="Operating_Systems_Notes.pdf",
            page_number=31,
            page_index=30,
            section_title="Virtual Memory and Page Faults"
        )
    ))

    # ==========================================
    # 2. DOCX - DBMS Architecture (doc-docx-02)
    # ==========================================
    doc_id_docx = "doc-docx-eval-02"
    corpus.append(DocumentChunk(
        chunk_id="chunk-docx-acid-1",
        content="Transaction management in database management systems guarantees reliable processing through the ACID properties: Atomicity guarantees that either all operations of the transaction succeed or none do (all-or-nothing). Consistency ensures that a transaction takes the database from one valid state to another valid state preserving all invariants. Isolation ensures that concurrent execution of transactions leaves the database in the same state as if transactions were executed sequentially. Durability guarantees that once a transaction commits, its updates persist even across system crashes or power failures.",
        metadata=ChunkMetadata(
            document_id=doc_id_docx,
            workspace_id=workspace_id,
            source_type=SourceType.DOCX,
            source_name="DBMS_Architecture.docx",
            file_name="DBMS_Architecture.docx",
            section_title="Transaction Management"
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-docx-bplus-1",
        content="B+ Tree indexing is widely utilized in relational databases for efficient disk block retrieval. All data pointers are stored in the leaf nodes, which are linked together in a sequential linked list for fast range scans. Internal nodes contain only routing keys and child page pointers, providing very high fanout and shallow tree depth typically between 3 and 4 levels.",
        metadata=ChunkMetadata(
            document_id=doc_id_docx,
            workspace_id=workspace_id,
            source_type=SourceType.DOCX,
            source_name="DBMS_Architecture.docx",
            file_name="DBMS_Architecture.docx",
            section_title="B+ Tree Indexing"
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-docx-mvcc-1",
        content="Multi-Version Concurrency Control (MVCC) enables concurrent reading and writing without read locks. In MVCC, each update generates a new version of the row tagged with the writing transaction ID. Readers view a consistent historical snapshot corresponding to their transaction start time, guaranteeing that readers never block writers and writers never block readers.",
        metadata=ChunkMetadata(
            document_id=doc_id_docx,
            workspace_id=workspace_id,
            source_type=SourceType.DOCX,
            source_name="DBMS_Architecture.docx",
            file_name="DBMS_Architecture.docx",
            section_title="Multi-Version Concurrency Control"
        )
    ))

    # ==========================================
    # 3. Markdown - Data Engineering Guide (doc-md-03)
    # ==========================================
    doc_id_md = "doc-md-eval-03"
    corpus.append(DocumentChunk(
        chunk_id="chunk-md-polars-1",
        content="### Performance Optimization\nPolars achieves significant performance gains over row-oriented Pandas by utilizing the Apache Arrow columnar format in memory. Columnar memory layout enhances CPU cache locality and allows modern SIMD vectorization across CPU registers. Because operations are applied to contiguous memory buffers without Python object overhead, memory footprint is drastically reduced and analytical queries execute order-of-magnitude faster.",
        metadata=ChunkMetadata(
            document_id=doc_id_md,
            workspace_id=workspace_id,
            source_type=SourceType.MARKDOWN,
            source_name="Data_Engineering_Guide.md",
            file_name="Data_Engineering_Guide.md",
            section_title="Performance Optimization"
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-md-kafka-1",
        content="### Distributed Messaging with Apache Kafka\nApache Kafka structures event streams into topics partitioned across broker nodes. A partition is an immutable append-only commit log ordered strictly by monotonically increasing offset IDs. Consumer groups distribute partition consumption such that each partition is assigned to exactly one consumer instance per group, enabling horizontal scalability with strict per-partition ordering.",
        metadata=ChunkMetadata(
            document_id=doc_id_md,
            workspace_id=workspace_id,
            source_type=SourceType.MARKDOWN,
            source_name="Data_Engineering_Guide.md",
            file_name="Data_Engineering_Guide.md",
            section_title="Distributed Messaging with Apache Kafka"
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-md-duckdb-1",
        content="### Embedded Analytics with DuckDB\nDuckDB is an in-process vectorized columnar database designed for fast analytical OLAP queries. Unlike SQLite which processes records row-by-row with Volcano iteration, DuckDB executes operations in vector batches of 2048 tuples, maximizing modern CPU instruction pipelining and zero-copy Arrow data exchange.",
        metadata=ChunkMetadata(
            document_id=doc_id_md,
            workspace_id=workspace_id,
            source_type=SourceType.MARKDOWN,
            source_name="Data_Engineering_Guide.md",
            file_name="Data_Engineering_Guide.md",
            section_title="Embedded Analytics with DuckDB"
        )
    ))

    # ==========================================
    # 4. TXT - Networking Protocols (doc-txt-04)
    # ==========================================
    doc_id_txt = "doc-txt-eval-04"
    corpus.append(DocumentChunk(
        chunk_id="chunk-txt-tcp-1",
        content="Transmission Control Protocol (TCP) uses a three-way handshake to establish a reliable stream connection between client and server: Step 1: The client sends a SYN (Synchronize Sequence Number) packet to the server to initiate connection. Step 2: The server responds with a SYN-ACK packet confirming receipt and synchronizing its own sequence number. Step 3: The client returns an ACK (Acknowledgment) packet back to the server, establishing the bidirectional connection state.",
        metadata=ChunkMetadata(
            document_id=doc_id_txt,
            workspace_id=workspace_id,
            source_type=SourceType.TXT,
            source_name="Networking_Protocols.txt",
            file_name="Networking_Protocols.txt",
            section_title="TCP Connection Establishment"
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-txt-dns-1",
        content="Domain Name System (DNS) maps human-readable hostnames to numerical IP addresses. Recursive DNS resolution starts at the local DNS resolver, queries root nameservers (.), moves to Top-Level Domain (TLD) servers (e.g. .com or .org), and finally queries authoritative nameservers holding the canonical A or AAAA records.",
        metadata=ChunkMetadata(
            document_id=doc_id_txt,
            workspace_id=workspace_id,
            source_type=SourceType.TXT,
            source_name="Networking_Protocols.txt",
            file_name="Networking_Protocols.txt",
            section_title="DNS Resolution Process"
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-txt-tls-1",
        content="Transport Layer Security (TLS 1.3) improves upon TLS 1.2 by reducing handshake latency to a single round-trip time (1-RTT) and offering zero round-trip (0-RTT) session resumption. It removes insecure cipher suites such as RC4, DES, and CBC-mode ciphers, mandating Ephemeral Diffie-Hellman for forward secrecy.",
        metadata=ChunkMetadata(
            document_id=doc_id_txt,
            workspace_id=workspace_id,
            source_type=SourceType.TXT,
            source_name="Networking_Protocols.txt",
            file_name="Networking_Protocols.txt",
            section_title="TLS 1.3 Security Enhancements"
        )
    ))

    # ==========================================
    # 5. CSV - Employee Directory (doc-csv-05)
    # ==========================================
    doc_id_csv = "doc-csv-eval-05"
    corpus.append(DocumentChunk(
        chunk_id="chunk-csv-row12",
        content="Employee ID: EMP-1092\nName: Rahul Sharma\nDepartment: Engineering\nRole: Principal Architect\nCompensation: $185,000\nLocation: Seattle\nTenure: 5 years",
        metadata=ChunkMetadata(
            document_id=doc_id_csv,
            workspace_id=workspace_id,
            source_type=SourceType.CSV,
            source_name="Employee_Directory.csv",
            file_name="Employee_Directory.csv",
            row_number=12
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-csv-row13",
        content="Employee ID: EMP-1093\nName: Sarah Jenkins\nDepartment: Marketing\nRole: Growth Director\nCompensation: $140,000\nLocation: New York\nTenure: 3 years",
        metadata=ChunkMetadata(
            document_id=doc_id_csv,
            workspace_id=workspace_id,
            source_type=SourceType.CSV,
            source_name="Employee_Directory.csv",
            file_name="Employee_Directory.csv",
            row_number=13
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-csv-row14",
        content="Employee ID: EMP-1094\nName: Alice Chen\nDepartment: Security\nRole: Senior Penetration Tester\nCompensation: $165,000\nLocation: San Francisco\nTenure: 4 years",
        metadata=ChunkMetadata(
            document_id=doc_id_csv,
            workspace_id=workspace_id,
            source_type=SourceType.CSV,
            source_name="Employee_Directory.csv",
            file_name="Employee_Directory.csv",
            row_number=14
        )
    ))

    # ==========================================
    # 6. XLSX - University Roster (doc-xlsx-06)
    # ==========================================
    doc_id_xlsx = "doc-xlsx-eval-06"
    corpus.append(DocumentChunk(
        chunk_id="chunk-xlsx-cs-row15",
        content="Sheet: Computer_Science | Row: 15\nRoll No: 1042\nStudent Name: Priya Patel\nMajor: Computer Science\nSemester: 6\nCGPA: 9.1\nAdvisor: Dr. Alan Turing\nStatus: Enrolled",
        metadata=ChunkMetadata(
            document_id=doc_id_xlsx,
            workspace_id=workspace_id,
            source_type=SourceType.XLSX,
            source_name="University_Roster.xlsx",
            file_name="University_Roster.xlsx",
            sheet_name="Computer_Science",
            row_number=15
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-xlsx-cs-row16",
        content="Sheet: Computer_Science | Row: 16\nRoll No: 1043\nStudent Name: David Kim\nMajor: Computer Science\nSemester: 6\nCGPA: 8.4\nAdvisor: Dr. Alan Turing\nStatus: Enrolled",
        metadata=ChunkMetadata(
            document_id=doc_id_xlsx,
            workspace_id=workspace_id,
            source_type=SourceType.XLSX,
            source_name="University_Roster.xlsx",
            file_name="University_Roster.xlsx",
            sheet_name="Computer_Science",
            row_number=16
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-xlsx-math-row8",
        content="Sheet: Mathematics | Row: 8\nRoll No: 2011\nStudent Name: Emma Watson\nMajor: Applied Mathematics\nSemester: 4\nCGPA: 9.6\nAdvisor: Dr. Katherine Johnson\nStatus: Enrolled",
        metadata=ChunkMetadata(
            document_id=doc_id_xlsx,
            workspace_id=workspace_id,
            source_type=SourceType.XLSX,
            source_name="University_Roster.xlsx",
            file_name="University_Roster.xlsx",
            sheet_name="Mathematics",
            row_number=8
        )
    ))

    # ==========================================
    # 7. Website - Web Protocols & Architecture (doc-web-07)
    # ==========================================
    doc_id_web = "doc-web-eval-07"
    corpus.append(DocumentChunk(
        chunk_id="chunk-web-http3-1",
        content="### QUIC Transport Layer\nHTTP/3 replaces TCP with QUIC, an encrypted transport protocol built on top of UDP. A primary benefit of QUIC is eliminating TCP head-of-line blocking. In TCP, if a single packet is lost in the stream, all subsequent streams are blocked until retransmission. In QUIC, independent multiplexed streams exist within UDP datagrams; packet loss in one stream only delays that specific stream, allowing unaffected streams to proceed without interruption.",
        metadata=ChunkMetadata(
            document_id=doc_id_web,
            workspace_id=workspace_id,
            source_type=SourceType.WEB,
            source_name="HTTP/3 and QUIC Protocol Guide",
            source_url="https://example.com/http3-quic-guide",
            section_title="QUIC Transport Layer"
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-web-ws-1",
        content="### WebSocket Full-Duplex Communication\nWebSockets provide persistent, low-latency, full-duplex communication over a single TCP socket. After an initial HTTP Upgrade handshake, client and server can transmit lightweight binary or text frames asynchronously without HTTP header overhead, making WebSockets ideal for financial tickers and real-time chat.",
        metadata=ChunkMetadata(
            document_id=doc_id_web,
            workspace_id=workspace_id,
            source_type=SourceType.WEB,
            source_name="HTTP/3 and QUIC Protocol Guide",
            source_url="https://example.com/websocket-guide",
            section_title="WebSocket Architecture"
        )
    ))

    # ==========================================
    # 8. YouTube - Technical Engineering Lectures (doc-yt-08)
    # ==========================================
    doc_id_yt = "doc-yt-eval-08"
    corpus.append(DocumentChunk(
        chunk_id="chunk-yt-backprop-1",
        content="[12:00 - 13:05] Now let's examine the backpropagation algorithm in neural networks. Backpropagation is fundamentally an efficient application of the calculus chain rule for computing partial derivatives of the loss function with respect to every weight in the network. We compute the forward activation pass, calculate the error at the output layer, and propagate gradients backwards layer by layer.",
        metadata=ChunkMetadata(
            document_id=doc_id_yt,
            workspace_id=workspace_id,
            source_type=SourceType.YOUTUBE,
            source_name="Deep Learning Lecture 4 - Optimization",
            source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            start_time=720.0,
            end_time=785.0,
            timestamp_str="12:00 - 13:05",
            section_title="Backpropagation and the Chain Rule"
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-yt-attention-1",
        content="[24:15 - 25:30] Self-attention in Transformer architectures computes dynamic contextual weights between tokens. For each token, we generate query, key, and value vectors via linear projections. The attention score is calculated as Softmax(Q * K^T / sqrt(d_k)) multiplied by the value vector V. The scaling factor sqrt(d_k) prevents dot products from growing excessively large in high dimensions, preventing small gradients during softmax.",
        metadata=ChunkMetadata(
            document_id=doc_id_yt,
            workspace_id=workspace_id,
            source_type=SourceType.YOUTUBE,
            source_name="Deep Learning Lecture 8 - Transformers",
            source_url="https://www.youtube.com/watch?v=m4aY0kLgXzQ",
            start_time=1455.0,
            end_time=1530.0,
            timestamp_str="24:15 - 25:30",
            section_title="Self-Attention and Scaled Dot-Product"
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-yt-raft-1",
        content="[05:10 - 06:45] The Raft consensus algorithm decomposes distributed state machine replication into three key subproblems: leader election, log replication, and safety. In Raft, a cluster has exactly one leader at any given term. If a follower detects election timeout without receiving heartbeats from the leader, it transitions to candidate state and requests votes.",
        metadata=ChunkMetadata(
            document_id=doc_id_yt,
            workspace_id=workspace_id,
            source_type=SourceType.YOUTUBE,
            source_name="Distributed Systems Lecture - Raft Consensus",
            source_url="https://www.youtube.com/watch?v=vYp4w123Abc",
            start_time=310.0,
            end_time=405.0,
            timestamp_str="05:10 - 06:45",
            section_title="Raft Consensus and Leader Election"
        )
    ))

    # ==========================================
    # 9. Realistic Distractor Chunks (doc-distract-09)
    # ==========================================
    doc_id_distract = "doc-distract-09"
    corpus.append(DocumentChunk(
        chunk_id="chunk-distract-recipe",
        content="To bake a classic dark chocolate soufflé, preheat the oven to 375 degrees Fahrenheit. Melt dark chocolate with unsalted butter over a double boiler, whip egg whites with sugar until stiff peaks form, and gently fold together before baking for 14 minutes.",
        metadata=ChunkMetadata(
            document_id=doc_id_distract,
            workspace_id=workspace_id,
            source_type=SourceType.TXT,
            source_name="Cooking_Recipes.txt",
            file_name="Cooking_Recipes.txt",
            section_title="Dessert Recipes"
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-distract-gardening",
        content="Perennial plants such as English lavender and purple coneflowers thrive in full sunlight and well-drained sandy loam soil. Prune dead foliage in early spring before new shoots emerge to promote vigorous blooming.",
        metadata=ChunkMetadata(
            document_id=doc_id_distract,
            workspace_id=workspace_id,
            source_type=SourceType.TXT,
            source_name="Gardening_Tips.txt",
            file_name="Gardening_Tips.txt",
            section_title="Perennial Plant Care"
        )
    ))
    corpus.append(DocumentChunk(
        chunk_id="chunk-distract-astronomy",
        content="Jupiter is the largest planet in our solar system, with a mass more than two and a half times that of all the other planets combined. Its Great Red Spot is a persistent anticyclonic storm larger than the Earth, known to have existed for at least 350 years.",
        metadata=ChunkMetadata(
            document_id=doc_id_distract,
            workspace_id=workspace_id,
            source_type=SourceType.MARKDOWN,
            source_name="Astronomy_Overview.md",
            file_name="Astronomy_Overview.md",
            section_title="Gas Giants"
        )
    ))

    return corpus
