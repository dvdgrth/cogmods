# RNN-model for predicting relational reasoning. 
# The model uses basic RNN-units.


import time

import collections

import numpy as np

import ccobra

import torch
import torch.nn as nn
import torch.optim as optim
import torchvision.transforms as transforms





class RNN(nn.Module):
    def __init__(self, input_size=8, hidden_size=64, output_size=8):
        super(RNN, self).__init__()
        
        self.n_layers = 2
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        #Defining the layers
        # RNN Layer
        self.rnn = nn.RNN(input_size, hidden_size, self.n_layers, batch_first=True)   
        # Fully connected layer
        self.fc = nn.Linear(hidden_size, output_size)
    
    def forward(self, x):
        
        batch_size = x.size(0)

        # Initializing hidden state
        hidden = self.init_hidden(batch_size)

        out, hidden = self.rnn(x, hidden)

        #Reshaping output for the fully connected layer.
        out = out.contiguous().view(-1, self.hidden_size)
        out = self.fc(out)
        
        return out, hidden
    
    def init_hidden(self, batch_size):
        # This method generates the first hidden state of zeros.
        hidden = torch.zeros(self.n_layers, batch_size, self.hidden_size)
        return hidden


# mapping of cardinal direction input
input_mppng =  {"north-west": [1,0,0,1], "north":[1,0,0,0], "north-east":[1,1,0,0],
                "west": [0,0,0,1], "east":[0,1,0,0],
                "south-west": [0,0,1,1], "south":[0,0,1,0], "south-east":[0,1,1,0]}

# mapping of cardinal direction output
output_mppng = {"north-west": [1,0,0,0,0,0,0,0], "north":[0,1,0,0,0,0,0,0], "north-east":[0,0,1,0,0,0,0,0],
                "west": [0,0,0,1,0,0,0,0], "east":[0,0,0,0,1,0,0,0],
                "south-west": [0,0,0,0,0,1,0,0], "south":[0,0,0,0,0,0,1,0], "south-east":[0,0,0,0,0,0,0,1]}

# Reverse mapping of turning a class label into a cardinal direction.
output_mpp_reverse = {0:"north-west", 1:"north", 2: "north-east",
                3:"west", 4:"east",
                5:"south-west", 6:"south", 7:"south-east"}




class RNNModel(ccobra.CCobraModel):
    def __init__(self, name='RNN', k=1):
        super(RNNModel, self).__init__(name, ["spatial-relational"], ["single-choice"])

        self.net = RNN()
        self.hidden = None


        self.n_epochs = 100

        self.optimizer = optim.Adam(self.net.parameters())
        self.loss = nn.CrossEntropyLoss()

    def pre_train(self, dataset):
        torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        
        x = []
        y = []

        for subj_train_data in dataset:
            subj_x = []
            subj_y = []
            for seq_train_data in subj_train_data:
                task = seq_train_data['item'].task

                inp = input_mppng[task[0][0]] + input_mppng[task[1][0]]
                target = output_mppng[seq_train_data['response'][0][0]]

                subj_x.append(inp)

                subj_y.append(target)

            x.append(subj_x)
            y.append(subj_y)
        x = np.array(x)
        y = np.array(y)

        self.train_x = torch.from_numpy(x).float()
        self.train_y = torch.from_numpy(y).float()


        self.train_network(self.train_x, self.train_y, self.n_epochs, verbose=True)



    def train_network(self, train_x, train_y, n_epochs, verbose=False):
        if verbose:
            print('Starting training...')
        for epoch in range(self.n_epochs):
            start_time = time.time()

            # Shuffle the training data
            perm_idxs = np.random.permutation(np.arange(len(train_x)))
            train_x = train_x[perm_idxs]
            train_y = train_y[perm_idxs]

            losses = []
            for idx in range(len(train_x)):
                cur_x = train_x[idx]
                cur_y = train_y[idx]

                inp = cur_x.view(-1,1,8)
                
                outputs, _ = self.net(inp)


                loss = self.loss(outputs.view(-1,8), cur_y.argmax(1))
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()

                losses.append(loss.item())

        if verbose:
            print('Epoch {}/{} ({:.2f}s): {:.4f} ({:.4f})'.format(
                epoch + 1, n_epochs, time.time() - start_time, np.mean(losses), np.std(losses)))

            accs = []
            for subj_idx in range(len(self.train_x)):
                pred, _ = self.net(self.train_x[subj_idx].view(-1,1,8))
                pred_max = pred.view(-1,8).argmax(1)
                truth = self.train_y[subj_idx].argmax(1)

                acc = torch.mean((pred_max == truth).float()).item()
                accs.append(acc)

            print('   acc mean: {:.2f}'.format(np.mean(accs)))
            print('   acc std : {:.2f}'.format(np.std(accs)))


        self.net.eval()


    # Turns the predicted, one-hot encoded output into class-label, which is further turned into a cardinal direction.      
    def predict(self, item, **kwargs):
        task = item.task
        x = torch.FloatTensor(input_mppng[task[0][0]] + input_mppng[task[1][0]])
        output, self.hidden = self.net(x.view(1, 1, -1))


        label = np.argmax(output.detach().numpy())
        self.prediction= [output_mpp_reverse[label], task[-1][-1], task[0][1]]
        return self.prediction

