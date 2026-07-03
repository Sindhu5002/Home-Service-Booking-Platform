USE homeserve_db;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20) NOT NULL,
    area VARCHAR(100) NOT NULL,
    password VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE services (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    image VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE workers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    phone VARCHAR(15) NOT NULL,
    aadhar VARCHAR(12),
    service_id INT NOT NULL,
    gender VARCHAR(10),
    experience INT, -- Professional years
    address VARCHAR(255),
    area VARCHAR(100),
    photo VARCHAR(255),
    status VARCHAR(20) DEFAULT 'Active',
    -- 🔥 NEW COLUMNS FOR BLUEPRINT
    is_busy BOOLEAN DEFAULT FALSE,      -- Set to 1 when job is 'Assigned'
    jobs_today INT DEFAULT 0,           -- Resets daily, must stay < 5
    total_jobs INT DEFAULT 0,           -- Lifetime jobs (Used to identify 'Rookies')
    rating DECIMAL(3, 2) DEFAULT 0.0,   -- Calculated from user feedback
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE bookings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    selected_worker_ids VARCHAR(255), -- Stores the 3 IDs (e.g., "10,15,22")
    assigned_worker_id INT DEFAULT NULL,
    base_price DECIMAL(10, 2),
    extra_charges DECIMAL(10, 2) DEFAULT 0.00,
    status ENUM('pending', 'assigned', 'arrived', 'in_progress', 'completed') DEFAULT 'pending',
    area VARCHAR(100),
    booking_date DATE,
    booking_time TIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE broadcast_queue (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT,
    worker_id INT,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
    FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE
);