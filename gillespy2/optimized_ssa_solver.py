import gillespy2
from gillespySolver import GillesPySolver
import random
import math
import numpy as np
import heapq
import numba

class SSASolver(GillesPySolver):
    """ TODO
    """

    def format_trajectories(simulation_data):
        out_data = []
        sorted_keys = sorted(simulation_data[0])
        sorted_keys.remove('time')
        for trajectory in simulation_data:
            columns = [np.vstack((trajectory['time'].T))]
            for column in sorted_keys:
                columns.append(np.vstack((trajectory[column].T)))
            out_array = np.hstack(columns)
            out_data.append(out_array)
        return out_data

    @classmethod
    def runArray(self, model, t=20, number_of_trajectories=1,
            increment=0.05, seed=None, debug=False, show_labels=False,stochkit_home=None):
        #create mapping of species dictionary to array indices
        species = list(model.listOfSpecies.keys())
        #create numpy array for timeline
        timeline = np.linspace(0, t, (t//increment+1))
        
        #create numpy matrix to mark other state data of species
        species_arr = np.zeros((timeline.size, len(species)))
        #copy initial values to base
        for i in range(len(species)):
            species_arr[0][i] = model.listOfSpecies[species[i]].initial_value 
        
        trajectory_base = species_arr

        #create dictionary of all constant parameters for propensity evaluation
        parameters = {'vol' : model.volume}
        for paramName, param in model.listOfParameters.items():
            parameters[paramName] = param.value
        
        #create an array mapping reactions to species modified
        species_changes = []
        #create mapping of reaction dictionary to array indices
        reactions = list(model.listOfReactions.keys())
        propensity_functions = [r.propensity_function for r in model.listOfReactions.values()]
        #pre-evaluate propensity equations from strings:
        for i in range(len(propensity_functions)):
            species_changes.append(np.zeros(len(species)))
            #replace all references to species with array indices
            for j in range(len(species)):
                if species[j] in propensity_functions[i]:
                    propensity_functions[i] = propensity_functions[i].replace(species[j], 'x[{0}]'.format(j))
                    #the change is positive for products, negative for reactants
                    species_changes[i][j] = model.listOfReactions[reactions[i]].products.get(species[j], -model.listOfReactions[reactions[i]].reactants.get(species[j]))
            propensity_functions[i] = eval('lambda x:'+propensity_functions[i], parameters)
        #map reactions to species they change
        reaction_changes = np.zeros((len(reactions),len(reactions)))
        #check all reaction changes for shared species
        for i in range(len(reactions)):
            for j in range(i+1,len(reactions)):
                if np.dot(np.absolute(species_changes[i]), np.absolute(species_changes[j])) != 0:
                    reaction_changes[i][j] = 1
                    reaction_changes[j][i] = 1
        
        #keep track of next reaction based on priority queue selection
        next_reaction = []
        #keep track of reactions popped off queue
        next_reaction_consumed = []
        #keep track of propensities evaluated each time step
        propensity_sums = np.zeros(len(reactions))
        #calculate initial propensity sums
        for i in range(len(propensity_sums)):
            propensity_sums[i] = propensity_functions[i](species_arr[0])
            heapq.push(next_reaction, (-propensity_sums[i], i))
        #begin simulating each trajectory
        self.simulation_data = []
        for trajectory_num in range(number_of_trajectories):
            #copy initial state data
            if trajectory_num == number_of_trajectories - 1:
                trajectory = trajectory_base
            else:
                trajectory = np.copy(trajectory_base)
            entry_count = 1 #the initial state is 0
            current_time = 0
            while entry_count < trajectory.shape[0]:
                reaction = -1
                #determine next reaction
                propensity_sum = random.uniform(0, np.sum(propensity_sums))
                #if no more reactions, quit
                if propensity_sum <= 0:
                    while entry_count < trajectory.shape[0]:
                        np.copyto(trajectory[entry_count-1], trajectory[entry_count])
                        entry_count += 1
                    break
                #determine time passed in this reaction
                current_time += math.log(random.random()) / propensity_sum
                while propensity_sum > 0:
                    reaction_popped = heapq.pop(next_reaction)
                    propensity_sum += reaction_popped[0]
                    if propensity_sum < 0:
                        reaction = reaction_popped[1]
                    next_reaction_consumed.append(reaction_popped[1])
                
            
    @classmethod
    def run(self, model, t=20, number_of_trajectories=1,
            increment=0.05, seed=None, debug=False, show_labels=False,stochkit_home=None):
        self.runArray(model,t,number_of_trajectories, increment, seed, debug, show_labels, stochkit_home)
        self.simulation_data = []
        curr_state = {}
        propensity = {}
        propensityFuns = {}
        for r in model.listOfReactions:
            propensityFuns[r] = eval('lambda :'+model.listOfReactions[r].propensity_function, curr_state)

        
        for traj_num in range(number_of_trajectories):
            trajectory = {}
            self.simulation_data.append(trajectory)
            trajectory['time'] = np.linspace(0,t,(t//increment+1))
            for s in model.listOfSpecies:   #Initialize Species population
                curr_state[s] = model.listOfSpecies[s].initial_value
                trajectory[s] = np.zeros(shape=(trajectory['time'].size))
            curr_state['vol'] = model.volume
            curr_time = 0	  
            entry_count = 0
            for p in model.listOfParameters:
                curr_state[p] = model.listOfParameters[p].value		

            reaction = None
            while(entry_count < trajectory['time'].size):
                prop_sum = 0
                for r in model.listOfReactions:
                    propensity[r] = (propensityFuns[r])()#eval(model.listOfReactions[r].propensity_function, curr_state)
                    prop_sum += propensity[r]
                cumil_sum = random.uniform(0,prop_sum)
                for r in model.listOfReactions:
                    cumil_sum -= propensity[r]
                    if(cumil_sum <= 0):
                        reaction = r
                        break
                if(prop_sum <= 0):
                    while(entry_count < trajectory['time'].size):
                        for s in model.listOfSpecies:
                            trajectory[s][entry_count]=(curr_state[s])
                        entry_count += 1
                    break

                tau = -1*math.log(random.random())/prop_sum
                curr_time += tau
                while(entry_count < trajectory['time'].size and curr_time >= trajectory['time'][entry_count]):
                    for s in model.listOfSpecies:
                        trajectory[s][entry_count]=(curr_state[s])
                    entry_count += 1

                for react in model.listOfReactions[reaction].reactants:
                    curr_state[str(react)] -=  model.listOfReactions[reaction].reactants[react]
                for prod in model.listOfReactions[reaction].products:
                    curr_state[str(prod)] += model.listOfReactions[reaction].products[prod]

        if show_labels:
            return self.simulation_data;
        else:
            return self.format_trajectories(self.simulation_data)
    


        
    def get_trajectories(self, outdir, debug=False, show_labels=False):
        pass
