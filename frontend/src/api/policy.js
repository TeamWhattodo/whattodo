import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL ?? '/api';

const axiosInstance = axios.create({
  baseURL: API_URL,
  withCredentials: true,
});

export const getPolicyList = async () => {
  const response = await axiosInstance.get(`/policy/list`);
  return response.data;
};

export const getPolicyStatus = async () => {
  const response = await axiosInstance.get(`/policy/status`);
  return response.data;
};

export const uploadPolicy = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await axiosInstance.post(`/policy/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return response.data;
};

export const triggerPolicyIngest = async (filename) => {
  const response = await axiosInstance.post(`/policy/ingest/${filename}`);
  return response.data;
};

export const deletePolicy = async (filename) => {
  const response = await axiosInstance.delete(`/policy/${filename}`);
  return response.data;
};

export const downloadPolicy = async (filename) => {
  const response = await axiosInstance.get(`/policy/files/${filename}`, {
    responseType: 'blob'
  });
  return response.data;
};
