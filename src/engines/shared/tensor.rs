// src/engines/shared/tensor.rs
use std::fmt;

#[derive(Clone)]
pub struct Tensor {
    pub data: Vec<f32>,
    pub shape: Vec<usize>,
}

impl Tensor {
    pub fn zeros(shape: &[usize]) -> Self {
        let size: usize = shape.iter().product();
        Self {
            data: vec![0.0; size],
            shape: shape.to_vec(),
        }
    }

    pub fn from_vec(data: Vec<f32>, shape: Vec<usize>) -> Self {
        Self { data, shape }
    }

    pub fn size_bytes(&self) -> usize {
        self.data.len() * std::mem::size_of::<f32>()
    }

    pub fn numel(&self) -> usize {
        self.data.len()
    }

    /// Matrix multiply: [M, K] x [K, N] -> [M, N]
    pub fn matmul(&self, other: &Tensor) -> Tensor {
        assert!(self.shape.len() == 2 && other.shape.len() == 2);
        let m = self.shape[0];
        let k = self.shape[1];
        let n = other.shape[1];
        assert_eq!(k, other.shape[0]);

        let mut result = vec![0.0f32; m * n];

        for i in 0..m {
            for j in 0..n {
                let mut sum = 0.0f32;
                for p in 0..k {
                    sum += self.data[i * k + p]
                        * other.data[p * n + j];
                }
                result[i * n + j] = sum;
            }
        }

        Tensor {
            data: result,
            shape: vec![m, n],
        }
    }

    pub fn add(&self, other: &Tensor) -> Tensor {
        assert_eq!(self.data.len(), other.data.len());
        let data: Vec<f32> = self.data.iter()
            .zip(other.data.iter())
            .map(|(a, b)| a + b)
            .collect();
        Tensor {
            data,
            shape: self.shape.clone(),
        }
    }

    pub fn rms_norm(&self, weight: &Tensor, eps: f32) -> Tensor {
        let n = self.data.len();
        let mean_sq: f32 = self.data.iter()
            .map(|x| x * x)
            .sum::<f32>() / n as f32;
        let scale = 1.0 / (mean_sq + eps).sqrt();

        let data: Vec<f32> = self.data.iter()
            .zip(weight.data.iter())
            .map(|(x, w)| x * scale * w)
            .collect();

        Tensor {
            data,
            shape: self.shape.clone(),
        }
    }

    pub fn softmax(&self) -> Tensor {
        let max_val = self.data.iter()
            .cloned()
            .fold(f32::NEG_INFINITY, f32::max);
        let exp_vals: Vec<f32> = self.data.iter()
            .map(|x| (x - max_val).exp())
            .collect();
        let sum: f32 = exp_vals.iter().sum();
        let data: Vec<f32> = exp_vals.iter()
            .map(|x| x / sum)
            .collect();

        Tensor {
            data,
            shape: self.shape.clone(),
        }
    }

    pub fn silu(&self) -> Tensor {
        let data: Vec<f32> = self.data.iter()
            .map(|&x| x / (1.0 + (-x).exp()))
            .collect();
        Tensor {
            data,
            shape: self.shape.clone(),
        }
    }

    pub fn element_multiply(&self, other: &Tensor) -> Tensor {
        assert_eq!(self.data.len(), other.data.len());
        let data: Vec<f32> = self.data.iter()
            .zip(other.data.iter())
            .map(|(a, b)| a * b)
            .collect();
        Tensor {
            data,
            shape: self.shape.clone(),
        }
    }

    pub fn argmax(&self) -> usize {
        self.data.iter()
            .enumerate()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap())
            .map(|(i, _)| i)
            .unwrap_or(0)
    }

    /// Sample from probability distribution with temperature
    pub fn sample(&self, temperature: f32) -> usize {
        if temperature <= 0.0 {
            return self.argmax();
        }

        let scaled: Vec<f32> = self.data.iter()
            .map(|x| x / temperature)
            .collect();

        let temp_tensor = Tensor {
            data: scaled,
            shape: self.shape.clone(),
        };
        let probs = temp_tensor.softmax();

        // Simple sampling
        let r: f32 = rand::random();
        let mut cumsum = 0.0;
        for (i, &p) in probs.data.iter().enumerate() {
            cumsum += p;
            if cumsum >= r {
                return i;
            }
        }
        probs.data.len() - 1
    }
}

impl fmt::Debug for Tensor {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "Tensor(shape={:?}, numel={}, bytes={})",
            self.shape,
            self.numel(),
            self.size_bytes()
        )
    }
}