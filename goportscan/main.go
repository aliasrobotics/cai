package main

import (
	"fmt"
	"net"
	"sort"
	"sync"
	"time"
)

func main() {
	target := "192.168.1.1"
	var wg sync.WaitGroup
	
	// Define the port range to scan
	startPort := 1
	endPort := 65535
	
	// Create a channel to collect open ports
	openPorts := make(chan int, 100)
	
	// Set timeout for connection attempts
	timeout := 500 * time.Millisecond
	
	// Start workers for parallel scanning
	numWorkers := 1000
	portsPerWorker := (endPort - startPort + 1) / numWorkers
	
	fmt.Printf("Starting ultra fast port scan on %s...\n", target)
	start := time.Now()
	
	// Launch workers
	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		workerStartPort := startPort + (i * portsPerWorker)
		workerEndPort := workerStartPort + portsPerWorker - 1
		
		// Adjust the last worker to include any remaining ports
		if i == numWorkers-1 {
			workerEndPort = endPort
		}
		
		go func(startP, endP int) {
			defer wg.Done()
			for port := startP; port <= endP; port++ {
				address := fmt.Sprintf("%s:%d", target, port)
				conn, err := net.DialTimeout("tcp", address, timeout)
				
				if err == nil {
					openPorts <- port
					conn.Close()
				}
			}
		}(workerStartPort, workerEndPort)
	}
	
	// Close the channel when all workers are done
	go func() {
		wg.Wait()
		close(openPorts)
	}()
	
	// Collect and display results
	var results []int
	for port := range openPorts {
		results = append(results, port)
	}
	
	// Sort and display results
	sort.Ints(results)
	
	fmt.Printf("\nScan completed in %s\n", time.Since(start))
	fmt.Printf("Open ports on %s:\n", target)
	
	if len(results) == 0 {
		fmt.Println("No open ports found")
	} else {
		for _, port := range results {
			fmt.Printf("%d/tcp open\n", port)
		}
		fmt.Printf("\nFound %d open ports\n", len(results))
	}
}
