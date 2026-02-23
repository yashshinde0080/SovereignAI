// src/vectorstore/hnsw.rs
use parking_lot::RwLock;
use std::collections::BinaryHeap;
use std::cmp::Ordering;

/// Simple HNSW-like approximate nearest neighbor index
pub struct HnswIndex {
    vectors: RwLock<Vec<Vec<f32>>>,
    dimension: usize,
    m: usize,       // Max connections per node
    ef: usize,      // Search expansion factor
}

#[derive(Debug, Clone)]
struct Neighbor {
    index: usize,
    distance: f32,
}

impl PartialEq for Neighbor {
    fn eq(&self, other: &Self) -> bool {
        self.distance == other.distance
    }
}

impl Eq for Neighbor {}

impl PartialOrd for Neighbor {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        // Reverse for min-heap behavior
        other.distance.partial_cmp(&self.distance)
    }
}

impl Ord for Neighbor {
    fn cmp(&self, other: &Self) -> Ordering {
        self.partial_cmp(other).unwrap_or(Ordering::Equal)
    }
}

impl HnswIndex {
    pub fn new(dimension: usize, m: usize, ef: usize) -> Self {
        Self {
            vectors: RwLock::new(Vec::new()),
            dimension,
            m,
            ef,
        }
    }

    pub fn insert(&self, vector: &[f32], _id: usize) {
        assert_eq!(vector.len(), self.dimension);
        self.vectors.write().push(vector.to_vec());
    }

    pub fn search(
        &self,
        query: &[f32],
        top_k: usize,
    ) -> Vec<(usize, f32)> {
        let vectors = self.vectors.read();

        let mut heap = BinaryHeap::new();

        for (i, vec) in vectors.iter().enumerate() {
            let dist = Self::cosine_similarity(query, vec);
            heap.push(Neighbor {
                index: i,
                distance: dist,
            });
        }

        let mut results = Vec::new();
        for _ in 0..top_k.min(heap.len()) {
            if let Some(n) = heap.pop() {
                results.push((n.index, n.distance));
            }
        }

        results
    }

    fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
        let dot: f32 = a.iter().zip(b.iter())
            .map(|(x, y)| x * y)
            .sum();
        let norm_a: f32 = a.iter()
            .map(|x| x * x)
            .sum::<f32>()
            .sqrt();
        let norm_b: f32 = b.iter()
            .map(|x| x * x)
            .sum::<f32>()
            .sqrt();

        if norm_a == 0.0 || norm_b == 0.0 {
            return 0.0;
        }

        dot / (norm_a * norm_b)
    }

    pub fn size(&self) -> usize {
        self.vectors.read().len()
    }
}