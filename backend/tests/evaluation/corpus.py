import uuid
from typing import List
from backend.app.schemas.document import DocumentChunk, ChunkMetadata, SourceType

def get_evaluation_corpus() -> List[DocumentChunk]:
    """
    Returns a multi-source evaluation corpus with target documents across
    all 8 supported source types and realistic distractors.
    """
    workspace_id = "eval-workspace"
    corpus: List[DocumentChunk] = []

    # 1. PDF - Operating Systems Notes
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
        content="CPU scheduling deals with the problem of deciding which of the processes in the ready queue is to be allocated the CPU. Scheduling algorithms include First-Come First-Served (FCFS), Shortest Job First (SJF), Round Robin (RR), and Multilevel Feedback Queue.",
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

    # 2. DOCX - DBMS Architecture
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
        content="B+ Tree indexing is widely utilized in relational databases for efficient disk block retrieval. All data pointers are stored in the leaf nodes, which are linked together in a sequential linked list for fast range scans.",
        metadata=ChunkMetadata(
            document_id=doc_id_docx,
            workspace_id=workspace_id,
            source_type=SourceType.DOCX,
            source_name="DBMS_Architecture.docx",
            file_name="DBMS_Architecture.docx",
            section_title="B+ Tree Indexing"
        )
    ))

    # 3. Markdown - Data Engineering Guide
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

    # 4. TXT - Networking Protocols
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

    # 5. CSV - Employee Directory
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

    # 6. XLSX - University Roster
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

    # 7. Website - HTTP/3 Guide
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

    # 8. YouTube - Deep Learning Lecture
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

    # 9. Distractor chunks (unrelated topics to test discrimination)
    doc_id_distract = "doc-distract-09"
    corpus.append(DocumentChunk(
        chunk_id="chunk-distract-recipe",
        content="To bake a classic dark chocolate soufflé, preheat the oven to 375 degrees Fahrenheit. Melt dark chocolate with unsalted butter over a double boiler, whip egg whites with sugar until stiff peaks form, and gently fold together.",
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
        content="Perennial plants such as lavender and coneflowers thrive in full sunlight and well-drained soil. Prune dead foliage in early spring before new shoots emerge to promote vigorous flowering.",
        metadata=ChunkMetadata(
            document_id=doc_id_distract,
            workspace_id=workspace_id,
            source_type=SourceType.TXT,
            source_name="Gardening_Tips.txt",
            file_name="Gardening_Tips.txt",
            section_title="Perennial Plant Care"
        )
    ))

    return corpus
